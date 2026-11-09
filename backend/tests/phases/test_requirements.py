import pytest

from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S
from wings.phases.requirements.schema import RequirementItem, assign_ids

R = P.REQUIREMENTS


def item(rid: str = "", title: str = "t") -> RequirementItem:
    return RequirementItem(id=rid, title=title, description="d")


def test_assign_ids_numbers_new_and_keeps_known():
    fresh = assign_ids([item("REQ-007"), item()], previous=[])
    assert [r.id for r in fresh] == ["REQ-001", "REQ-002"]  # ids from the LLM are not trusted on a first draft
    revised = assign_ids([item("REQ-002"), item(), item("REQ-002")], previous=["REQ-001", "REQ-002"])
    assert [r.id for r in revised] == ["REQ-002", "REQ-003", "REQ-004"]  # duplicates get new ids, REQ-001 is never reused


def test_questions_first_then_requirements(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = orch.create_project("Todo").id

    asked = orch.run_action(pid, R, "start", {"description": "A todo app"})
    assert asked.project.status(R) is S.NEEDS_INPUT
    assert asked.outcome.artifacts == []
    assert [q["id"] for q in asked.outcome.data["questions"]] == ["Q1", "Q2", "Q3"]

    drafted = orch.run_action(pid, R, "answer", {"answers": "CLI, due date, yes file"})
    assert drafted.project.status(R) is S.DRAFT
    req = drafted.outcome.artifacts[0]
    assert req.defines == ["REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005"]
    assert req.path == "requirements.md" and "### REQ-003 Complete a task (must)" in req.text

    # The answer turn sees the whole conversation: description, questions, answers.
    last_call = orch.llm.calls[-1]
    assert [t.role for t in last_call.messages] == ["user", "assistant", "user"]


def test_discuss_changes_nothing(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = orch.create_project("Todo").id
    orch.run_action(pid, R, "start", {"description": "A todo app"})
    orch.run_action(pid, R, "answer", {"answers": "CLI"})
    before = orch.project(pid).status(R)
    talk = orch.run_action(pid, R, "discuss", {"question": "Where does REQ-005 come from?"})
    assert "REQ-005" in talk.outcome.reply
    assert talk.outcome.artifacts == [] and talk.project.status(R) is before


def test_developer_edit_regenerates_markdown_and_keeps_ids(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = orch.create_project("Todo").id
    orch.run_action(pid, R, "start", {"description": "x"})
    req = orch.run_action(pid, R, "answer", {"answers": "y"}).outcome.artifacts[0]
    content = req.content
    content["requirements"][0]["title"] = "Add a task quickly"
    content["requirements"].append({"title": "Undo", "description": "Undo the last change"})
    edited, _ = orch.update_artifact(pid, "requirements", content=content)
    assert edited.defines[-1] == "REQ-006"
    assert "### REQ-001 Add a task quickly" in edited.text
    with pytest.raises(ValueError):
        orch.update_artifact(pid, "requirements", text="free text")


def test_revise_without_requirements_is_rejected(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = orch.create_project("Todo").id
    with pytest.raises(Exception, match="no requirements"):
        orch.run_action(pid, R, "revise", {"feedback": "more"})
