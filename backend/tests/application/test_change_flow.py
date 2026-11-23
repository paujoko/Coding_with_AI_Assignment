"""A change request carried through every phase: progress, one phase per call, the receipt (criterion C2).

Runs on the demo script, whose 'task priority' scenario gives every wing a really different output.
"""

import copy

import pytest

from wings.adapters.sandbox import LocalSandbox
from wings.domain.errors import NotFoundError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S

REQUEST = "Tasks need a priority"
TRACKED = [P.REQUIREMENTS, P.DESIGN, P.REFINEMENT, P.CODEGEN, P.TESTING, P.DEPLOYMENT]


@pytest.fixture
def maintained(make_orchestrator, demo_script, walk):
    def build(script=None):
        orch = make_orchestrator(script or demo_script)
        orch.sandbox = LocalSandbox()
        return orch, walk(orch, P.MAINTENANCE)

    return build


def carry_through(orch, pid, number=1, limit=10):
    results = []
    for _ in range(limit):
        result = orch.advance_change(pid, number)
        results.append(result)
        if result.stopped_reason is not None or result.change.state != "open":
            break
    return results


def test_a_change_request_records_a_baseline_and_starts_open(maintained):
    orch, pid = maintained()
    assert orch.changes(pid) == [] and orch.open_change(pid) is None
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    record = orch.store.get_artifact(pid, "change-1")
    assert record.content["baseline"]["requirements"] == {"revision": 1, "retired": False, "digest": record.content["baseline"]["requirements"]["digest"]}
    assert "source-todo-service-py" in record.content["baseline"]
    [change] = orch.changes(pid)
    assert (change.number, change.kind, change.request, change.state) == (1, "change", REQUEST, "open")
    assert change.affected == ["REQ-001", "REQ-002"] and change.completed_at is None
    assert [p.state for p in change.progress.phases] == ["current", "waiting", "waiting", "waiting", "waiting", "waiting"]
    assert [p.title for p in change.progress.phases][:2] == ["Requirements", "Design"]
    assert (change.next.kind, change.next.phase, change.next.action) == ("run", P.REQUIREMENTS, "revise")
    assert "priority" in change.next.input["feedback"]
    assert all(r.count == 0 for r in change.receipt)
    found = orch.open_change(pid)
    assert (found.number, found.done, found.total, found.next_phase) == (1, 0, 6, P.REQUIREMENTS)


def test_advance_runs_one_phase_per_call_and_approves_on_the_developers_behalf(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    first = orch.advance_change(pid, 1)
    assert [(r.phase, r.action, r.status) for r in first.ran] == [(P.REQUIREMENTS, "revise", S.DRAFT)]
    assert first.approved is P.REQUIREMENTS and first.stopped_reason is None
    assert first.project.status(P.REQUIREMENTS) is S.APPROVED and first.project.status(P.DESIGN) is S.STALE
    assert [p.state for p in first.change.progress.phases] == ["done", "current", "waiting", "waiting", "waiting", "waiting"]
    assert (first.change.next.phase, first.change.next.action) == (P.DESIGN, "revise")
    approvals = [e for e in orch.store.list_events(pid) if e.kind == "phase.approved" and e.data.get("change") == 1]
    assert len(approvals) == 1 and "change #1" in approvals[0].summary and "at the developer's request" in approvals[0].summary
    assert approvals[0].data["on_behalf"] is True


def test_the_whole_change_is_carried_through_and_the_receipt_names_every_artifact(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    results = carry_through(orch, pid)
    assert [r.approved for r in results] == TRACKED
    assert all(r.stopped_reason is None for r in results)
    assert [(s.action) for s in results[4].ran] == ["generate", "run"]  # tests are written, then run for real

    [change] = orch.changes(pid)
    assert change.state == "complete" and change.completed_at is not None and change.next is None
    assert [p.state for p in change.progress.phases] == ["done"] * 6
    assert orch.open_change(pid) is None
    receipt = {r.phase: r for r in change.receipt}
    requirements = receipt[P.REQUIREMENTS].updated[0]
    assert (requirements.id, requirements.before, requirements.after, requirements.changed) == ("requirements", 1, 2, True)
    changed = {a.id for r in change.receipt for a in r.updated if a.changed}
    assert {"requirements", "diagram-domain-classes", "refined-domain-classes", "source-todo-models-py", "source-todo-service-py", "test-test-tasks-py", "deploy-deploy-md"} <= changed
    same = {a.id for r in change.receipt for a in r.updated if not a.changed}
    assert any(i.startswith("source-") for i in same)  # files the coder wrote again without a difference say so
    assert all(r.count for r in change.receipt)
    # the real program got the feature, and the tests that ran prove it
    assert "priority" in orch.store.get_artifact(pid, "source-todo-models-py").text
    report = orch.store.get_artifact(pid, "test-report")
    assert report.content["green"] and report.content["passed"] == 11
    # the change artifact keeps the receipt, so a later change does not rewrite it
    record = orch.store.get_artifact(pid, "change-1")
    assert record.content["closed"]["completed_at"] and "## Carried through" in record.text
    assert any(e.kind == "change.completed" for e in orch.store.list_events(pid))
    again = orch.advance_change(pid, 1)
    assert again.ran == [] and "complete" in again.stopped_reason


def test_a_closed_change_keeps_its_receipt_when_the_next_change_moves_the_artifacts(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    carry_through(orch, pid)
    before = orch.changes(pid)[0].receipt
    orch.run_action(pid, P.MAINTENANCE, "check", {})
    orch.approve(pid, P.MAINTENANCE)
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "Another one"})
    orch.advance_change(pid, 2)
    second, first = orch.changes(pid)
    assert (second.number, second.state, first.number, first.state) == (2, "open", 1, "complete")
    assert first.receipt == before
    assert second.receipt[0].updated[0].before == 2


def test_without_approval_the_change_stops_for_review_and_goes_on_after_it(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    result = orch.advance_change(pid, 1, approve=False)
    assert result.approved is None and "Accept it" in result.stopped_reason
    assert result.project.status(P.REQUIREMENTS) is S.DRAFT
    assert result.change.next.kind == "approve"
    orch.approve(pid, P.REQUIREMENTS)  # the developer's own approval counts the same
    assert orch.changes(pid)[0].next.phase is P.DESIGN


def test_a_failed_gate_stops_the_change_with_the_reason(maintained, demo_script):
    script = copy.deepcopy(demo_script)
    key = next(k for k in script if k.startswith("tester?"))
    script[key][0]["files"][0]["content"] += "\n\ndef test_req_001_always_fails():\n    assert False\n"
    orch, pid = maintained(script)
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    results = carry_through(orch, pid)
    last = results[-1]
    assert [r.approved for r in results] == [P.REQUIREMENTS, P.DESIGN, P.REFINEMENT, P.CODEGEN, None]
    assert "do not pass" in last.stopped_reason and [s.action for s in last.ran] == ["generate", "run"]
    assert last.project.status(P.TESTING) is S.DRAFT
    assert (last.change.next.kind, last.change.next.phase) == ("blocked", P.TESTING)
    stopped = orch.advance_change(pid, 1)  # nothing runs again while the gate is closed
    assert stopped.ran == [] and "do not pass" in stopped.stopped_reason
    assert any(e.kind == "change.stopped" for e in orch.store.list_events(pid))


def test_a_failing_action_stops_the_change_and_saves_nothing(maintained):
    orch, pid = maintained()
    orch.llm._script = {k: v for k, v in orch.llm._script.items() if not k.startswith("architect")}  # the provider fails from here on
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    orch.advance_change(pid, 1)
    failed = orch.advance_change(pid, 1)
    assert failed.ran == [] and failed.approved is None
    assert "did not finish" in failed.stopped_reason and "architect" in failed.stopped_reason
    assert failed.project.status(P.DESIGN) is S.STALE


def test_open_questions_stop_the_change(maintained, demo_script):
    script = copy.deepcopy(demo_script)
    key = next(k for k in script if k.startswith("analyst?"))
    script[key] = [{"summary": "Unclear.", "questions": [{"id": "Q1", "question": "How many priorities?", "why": "Decides the values."}], "requirements": [], "assumptions": []}]
    orch, pid = maintained(script)
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    result = orch.advance_change(pid, 1)
    assert result.approved is None and "open questions" in result.stopped_reason
    assert result.change.next.kind == "input"
    assert orch.advance_change(pid, 1).ran == []


def test_a_bug_starts_in_the_code_and_leaves_the_design_untouched(maintained, demo_script):
    script = copy.deepcopy(demo_script)
    script["impact_analyst"] = [{"kind": "bug", "summary": "Deleting task 2 deletes task 1.", "affected": ["REQ-004"], "fix": "Compare numbers, not positions.", "steps": ["Code: fix delete."]}]
    orch, pid = maintained(script)
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "delete removes the wrong task"})
    change = orch.changes(pid)[0]
    assert [p.state for p in change.progress.phases] == ["untouched", "untouched", "untouched", "current", "waiting", "waiting"]
    assert (change.next.phase, change.next.action, change.next.input) == (P.CODEGEN, "revise", {"feedback": "Compare numbers, not positions."})
    results = carry_through(orch, pid)
    assert [r.approved for r in results] == [P.CODEGEN, P.TESTING, P.DEPLOYMENT]
    done = orch.changes(pid)[0]
    assert done.state == "complete" and (done.progress.done, done.progress.total) == (3, 3)
    assert [r.count > 0 for r in done.receipt] == [False, False, False, True, True, True]


def test_a_change_that_was_never_started_is_dropped_by_the_next_one(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "one"})
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "two"})
    second, first = orch.changes(pid)
    assert (second.state, first.state, first.next) == ("open", "dropped", None)
    assert orch.open_change(pid).number == 2
    assert "nothing left" in orch.advance_change(pid, 1).stopped_reason


def test_unknown_change_is_not_found(maintained):
    orch, pid = maintained()
    with pytest.raises(NotFoundError):
        orch.advance_change(pid, 7)


def test_a_finished_change_runs_the_consistency_check_by_itself(make_orchestrator, demo_script, walk):
    """Session s06: after the last step Maintenance was left out of date with 'Check'; the check is code only."""
    from wings.adapters.sandbox import LocalSandbox
    from wings.domain.phases import PhaseId as P

    orch = make_orchestrator(demo_script)
    orch.sandbox = LocalSandbox()
    pid = walk(orch, P.MAINTENANCE)
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "Tasks need a priority (low, normal, high) and the list should be sorted by it."})
    for _ in range(8):
        result = orch.advance_change(pid, 1)
        if result.change.state == "complete" or result.stopped_reason:
            break
    assert result.change.state == "complete", result.stopped_reason
    checks = [a for a in orch.store.list_artifacts(pid) if a.id == "consistency"]
    assert checks and checks[-1].created_at >= result.change.completed_at
    assert orch.project(pid).status(P.MAINTENANCE).value == "draft"


def approve_stale_phases_without_running_them(orch, pid):
    """What the owner did in the flappy-bird project: the UI offered 'Approve' on stale phases."""
    for _ in range(2):
        orch.advance_change(pid, 1)  # requirements and design are really revised
    for ph in (P.REFINEMENT, P.CODEGEN, P.TESTING, P.DEPLOYMENT):
        assert orch.project(pid).status(ph) is S.STALE
        orch.approve(pid, ph)


def test_phases_approved_without_being_updated_do_not_complete_the_change(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    approve_stale_phases_without_running_them(orch, pid)
    [change] = orch.changes(pid)
    assert change.state == "open" and change.completed_at is None
    assert [p.state for p in change.progress.phases] == ["done", "done", "current", "waiting", "waiting", "waiting"]
    assert (change.next.phase, change.next.kind) == (P.REFINEMENT, "run")
    assert orch.open_change(pid).next_phase is P.REFINEMENT
    assert "closed" not in orch.store.get_artifact(pid, "change-1").content  # no receipt was frozen
    assert orch.store.get_artifact(pid, "source-todo-service-py").revision == 1  # the code never changed

    results = carry_through(orch, pid)  # the rest is really carried through
    assert [r.approved for r in results] == [P.REFINEMENT, P.CODEGEN, P.TESTING, P.DEPLOYMENT]
    done = orch.changes(pid)[0]
    assert done.state == "complete" and all(p.state == "done" for p in done.progress.phases)
    assert orch.store.get_artifact(pid, "source-todo-service-py").revision > 1
    assert orch.store.get_artifact(pid, "change-1").content["closed"]["progress"]["planned"] == [p.value for p in TRACKED]


def test_an_earlier_closed_but_unfinished_change_is_reopened_and_closed_again_with_a_fresh_receipt(maintained):
    """Data written before the fix: a change frozen while planned phases were never updated."""
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": REQUEST})
    approve_stale_phases_without_running_them(orch, pid)
    record = orch.store.get_artifact(pid, "change-1")
    legacy = {"completed_at": "2026-11-23T12:15:35+00:00", "progress": {"phases": [], "complete": True, "done": 2, "total": 2}, "receipt": []}
    orch._save(pid, record.model_copy(update={"content": record.content | {"closed": legacy}, "text": (record.text or "") + "\n\n## Carried through\n\nstale receipt"}))
    [change] = orch.changes(pid)
    assert change.state == "open" and change.completed_at is None  # not trusted, shown live
    carry_through(orch, pid)
    [change] = orch.changes(pid)
    assert change.state == "complete" and change.completed_at is not None
    record = orch.store.get_artifact(pid, "change-1")
    assert record.content["closed"]["progress"]["planned"] and record.text.count("## Carried through") == 1
    assert any(r.phase is P.CODEGEN and r.count for r in change.receipt)
