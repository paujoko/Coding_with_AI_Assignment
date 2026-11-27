"""The conversation of every step tells the whole story (ADR 0022): every choice and decision of the developer is a
line in the step it belongs to, and what Wings did on the developer's behalf is marked as Wings', never as theirs."""

import pytest

from wings.adapters.sandbox import LocalSandbox
from wings.application.agent import turns_from
from wings.domain.activity import WINGS, Message, Role, decision, for_agents, instruction
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S


@pytest.fixture
def built(make_orchestrator, demo_script, walk):
    """An orchestrator on the demo script with a sandbox, and a walk to any phase."""

    def build(phase: P = P.MAINTENANCE):
        orch = make_orchestrator(demo_script)
        orch.sandbox = LocalSandbox()
        return orch, walk(orch, phase)

    return build


def said(orch, pid, phase) -> list[tuple[str, str, str]]:
    """(role, author, text) of every message of a phase, in order."""
    return [(m.role.value, m.author, m.text) for m in orch.store.list_messages(pid, phase)]


def decisions(orch, pid, phase) -> list[Message]:
    return [m for m in orch.store.list_messages(pid, phase) if m.is_decision]


def mine(orch, pid, phase) -> list[Message]:
    """Messages stored as the developer's."""
    return [m for m in orch.store.list_messages(pid, phase) if m.role is Role.DEVELOPER or m.author == "developer"]


# The messages themselves


def test_decision_lines_never_reach_a_model_and_instructions_from_wings_do():
    ph = P.DESIGN
    messages = [
        Message(phase=ph, role=Role.DEVELOPER, text="Keep it small", author="developer"),
        decision(ph, "Draw: Class. Level: simple.", "generate"),
        Message(phase=ph, role=Role.AGENT, text="2 diagrams ready.", author="Design"),
        decision(ph, "Accepted", "approve"),
        instruction(ph, "The requirements changed. Update every diagram.", "revise", "Revise", {"catch_up": True}),
        decision(ph, "Accepted on your behalf", "approve", on_behalf={"catch_up": True}),
    ]
    assert [m.text for m in for_agents(messages)] == ["Keep it small", "2 diagrams ready.", "The requirements changed. Update every diagram."]
    assert [(t.role, t.content) for t in turns_from(messages)] == [
        ("user", "Keep it small"),
        ("assistant", "2 diagrams ready."),
        ("user", "The requirements changed. Update every diagram."),
    ]


def test_what_wings_does_on_behalf_is_never_the_developers():
    line = decision(P.DESIGN, "Accepted on your behalf", "approve", on_behalf={"change": 1})
    words = instruction(P.DESIGN, "Update the diagrams.", "revise", "Revise", {"change": 1})
    for m in (line, words):
        assert (m.role, m.author, m.on_behalf) == (Role.SYSTEM, WINGS, True)
    assert line.is_decision and not words.is_decision


def test_old_messages_without_the_new_fields_load_and_read_as_before():
    old = Message.model_validate({"phase": "design", "role": "developer", "text": "Q1: CLI", "author": "developer", "data": {}, "created_at": "2026-11-20T10:00:00Z"})
    assert not old.is_decision and not old.on_behalf
    assert [t.content for t in turns_from([old])] == ["Q1: CLI"]


# What run_action records


def test_a_choice_is_recorded_before_the_words_and_the_choice_is_not_sent_as_a_turn(built):
    orch, pid = built(P.DESIGN)
    orch.run_action(pid, P.DESIGN, "generate", {"kinds": ["class", "use_case"], "level": "detailed", "guidance": "Keep it small"})
    roles = [(m.role.value, m.text) for m in orch.store.list_messages(pid, P.DESIGN)]
    assert roles[0][0] == "developer" and roles[0][1].startswith("Draw: ")
    assert roles[1] == ("developer", "Keep it small") and roles[2][0] == "agent"
    [line] = decisions(orch, pid, P.DESIGN)
    assert line.text == "Draw: use case, class · detailed"  # reading order, whatever order they were ticked in
    assert line.data["decision"] == {"action": "generate", "kinds": ["class", "use_case"], "level": "detailed"}
    request = [c for c in orch.llm.calls if c.agent == "architect"][-1]
    assert not any(t.content.startswith("Draw: ") for t in request.messages)


def test_a_button_without_words_is_a_decision_line(built):
    orch, pid = built(P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    [line] = decisions(orch, pid, P.CODEGEN)
    assert (line.role, line.author, line.text) == (Role.DEVELOPER, "developer", "Generate code")


def test_tests_record_depth_run_and_injected_bugs(built):
    orch, pid = built(P.TESTING)
    orch.run_action(pid, P.TESTING, "generate", {"depth": "focused"})
    orch.run_action(pid, P.TESTING, "run", {})
    orch.run_action(pid, P.TESTING, "probe", {"limit": 2})
    assert [m.text for m in decisions(orch, pid, P.TESTING)] == ["Write focused tests", "Run the tests", "Inject up to 2 bugs, one at a time"]


def test_tests_written_again_without_a_depth_name_the_depth_they_keep(built):
    orch, pid = built(P.TESTING)
    orch.run_action(pid, P.TESTING, "generate", {"depth": "thorough"})
    orch.run_action(pid, P.TESTING, "generate", {"guidance": "Cover the empty list"})
    assert [m.text for m in mine(orch, pid, P.TESTING)] == ["Write thorough tests", "Write the tests again (thorough)", "Cover the empty list"]


def test_applied_findings_are_named_with_what_they_were_about(built):
    orch, pid = built(P.REFINEMENT)
    orch.run_action(pid, P.REFINEMENT, "review", {})
    review = orch.store.get_artifact(pid, "review")
    first = review.content["findings"][0]
    orch.run_action(pid, P.REFINEMENT, "apply", {"findings": ["f1"]})
    lines = [m.text for m in decisions(orch, pid, P.REFINEMENT)]
    assert lines[0] == "Review design"
    assert lines[1].startswith("Apply F1") and first["diagram"] in lines[1]
    assert decisions(orch, pid, P.REFINEMENT)[1].data["decision"]["findings"] == ["f1"]  # the input as sent


def test_accepting_a_review_with_open_findings_says_which_were_not_applied(built):
    orch, pid = built(P.REFINEMENT)
    orch.run_action(pid, P.REFINEMENT, "review", {})
    ids = [f["id"] for f in orch.store.get_artifact(pid, "review").content["findings"]]
    orch.approve(pid, P.REFINEMENT)
    assert decisions(orch, pid, P.REFINEMENT)[-1].text == f"Accepted without applying {', '.join(ids)}"


def test_a_failed_action_records_no_decision(built):
    orch, pid = built(P.DESIGN)
    orch.llm._script = {k: v for k, v in orch.llm._script.items() if not k.startswith("architect")}
    with pytest.raises(Exception):
        orch.run_action(pid, P.DESIGN, "generate", {})
    assert orch.store.list_messages(pid, P.DESIGN) == []


# Approvals, reopen, edits, folder


def test_accept_keep_and_reopen_are_lines_in_their_step(built):
    orch, pid = built(P.MAINTENANCE)
    assert decisions(orch, pid, P.DESIGN)[-1].text == "Accepted"
    orch.reopen(pid, P.DEPLOYMENT)
    assert decisions(orch, pid, P.DEPLOYMENT)[-1].text == "Reopened"
    orch.approve(pid, P.DEPLOYMENT)
    orch.run_action(pid, P.REQUIREMENTS, "revise", {"feedback": "Tasks need a priority"})
    orch.approve(pid, P.REQUIREMENTS)
    assert orch.project(pid).status(P.DESIGN) is S.STALE
    orch.approve(pid, P.DESIGN)  # Keep it unchanged
    kept = decisions(orch, pid, P.DESIGN)[-1]
    assert kept.text == "Kept unchanged, although Requirements changed" and kept.data["decision"]["kept"] is True


def test_the_tests_approval_note_goes_with_the_line_as_wings_note(built):
    orch, pid = built(P.DEPLOYMENT)
    accepted = decisions(orch, pid, P.TESTING)[-1]
    assert accepted.text == "Accepted" and "verified" in accepted.data["note"]


def test_an_edit_by_hand_is_a_line_with_the_new_revision(built):
    orch, pid = built(P.DESIGN)
    requirements = orch.store.get_artifact(pid, "requirements")
    saved, _ = orch.update_artifact(pid, "requirements", content=requirements.content)
    line = decisions(orch, pid, P.REQUIREMENTS)[-1]
    assert line.text == f"Edited {requirements.path} (revision {saved.revision})"
    assert line.data["decision"] == {"action": "edit", "artifact": "requirements", "revision": saved.revision}


def test_an_import_from_the_folder_is_the_developers_line_before_the_check(built, tmp_path):
    orch, pid = built(P.MAINTENANCE)
    from wings.adapters.project_folder import LocalProjectFolder

    orch.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home")
    folder = tmp_path / "mine"
    orch.set_folder(pid, str(folder))
    models = folder / "todo" / "models.py"
    models.write_text(models.read_text(encoding="utf-8") + "\n# by hand\n", encoding="utf-8")
    orch.import_folder_changes(pid)
    entries = orch.store.list_messages(pid, P.CODEGEN)
    line = next(m for m in entries if m.is_decision and m.data["decision"]["action"] == "import")
    assert (line.role, line.text) == (Role.DEVELOPER, "Imported from your folder: todo/models.py (changed)")
    assert entries.index(line) < next(i for i, m in enumerate(entries) if m.author == "Folder sync (code)")
    models.write_text(models.read_text(encoding="utf-8") + "\n# again\n", encoding="utf-8")
    orch.restore_folder_files(pid, ["todo/models.py"])
    assert decisions(orch, pid, P.CODEGEN)[-1].text == "Put the last written version back in your folder: todo/models.py"


# On the developer's behalf


def test_catching_up_marks_the_instruction_and_the_approval_as_wings(built):
    orch, pid = built(P.MAINTENANCE)
    orch.run_action(pid, P.REQUIREMENTS, "revise", {"feedback": "Tasks need a priority"})
    orch.approve(pid, P.REQUIREMENTS)
    before = len(orch.store.list_messages(pid, P.DESIGN))
    orch.catch_up(pid)
    new = orch.store.list_messages(pid, P.DESIGN)[before:]
    assert [(m.role, m.author) for m in new] == [(Role.SYSTEM, WINGS), (Role.AGENT, "Design"), (Role.SYSTEM, WINGS)]
    words, reply, approval = new
    assert words.text.startswith("The requirements changed.") and words.data["on_behalf"] == {"catch_up": True}
    assert words.data["action"] == "revise" and not words.is_decision
    assert approval.is_decision and approval.text == "Accepted on your behalf: its checks pass"
    # The instruction still reaches the architect as a user turn.
    request = [c for c in orch.llm.calls if c.agent == "architect"][-1]
    assert any(t.role == "user" and t.content == words.text for t in request.messages)


def test_a_change_carried_through_never_puts_words_in_the_developers_mouth(built):
    orch, pid = built(P.MAINTENANCE)
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "Tasks need a priority"})
    assert [m.text for m in mine(orch, pid, P.MAINTENANCE)] == ["Tasks need a priority"]
    counts = {ph: len(orch.store.list_messages(pid, ph)) for ph in P}
    for _ in range(8):
        result = orch.advance_change(pid, 1)
        if result.stopped_reason or result.change.state != "open":
            break
    assert orch.changes(pid)[0].state == "complete"
    for ph in P:
        new = orch.store.list_messages(pid, ph)[counts[ph] :]
        assert not [m for m in new if m.role is Role.DEVELOPER or m.author == "developer"], ph
        assert all(m.data["on_behalf"].get("change") == 1 for m in new if m.role is Role.SYSTEM), ph
    first = orch.store.list_messages(pid, P.REQUIREMENTS)[counts[P.REQUIREMENTS]]
    plan = orch.store.get_artifact(pid, "change-1").content["first_step"]["input"]["feedback"]
    assert (first.author, first.text) == (WINGS, plan)  # the analyst's planned revision, sent by Wings
    check = orch.store.list_messages(pid, P.MAINTENANCE)[counts[P.MAINTENANCE]]
    assert check.is_decision and check.author == WINGS and check.text == "Check consistency"


def test_redo_without_approval_leaves_the_accept_to_the_developer(built):
    orch, pid = built(P.MAINTENANCE)
    orch.run_action(pid, P.REQUIREMENTS, "revise", {"feedback": "Tasks need a priority"})
    orch.approve(pid, P.REQUIREMENTS)
    before = len(orch.store.list_messages(pid, P.DESIGN))
    orch.catch_up(pid, approve=False)
    orch.approve(pid, P.DESIGN)
    new = orch.store.list_messages(pid, P.DESIGN)[before:]
    assert [(m.author, m.is_decision) for m in new] == [(WINGS, False), ("Design", False), ("developer", True)]
    assert new[-1].text == "Accepted"
