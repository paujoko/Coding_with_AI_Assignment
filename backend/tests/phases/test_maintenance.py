"""P7 Maintenance: change requests with impact computed from the trace, and a consistency check by code."""

import copy

import pytest

from wings.adapters.sandbox import LocalSandbox
from wings.application.phase import PhaseContext
from wings.application.ports import ReadOnlyStore
from wings.domain.errors import InvalidTransitionError, PhaseLockedError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S
from wings.phases.maintenance import MODULE


@pytest.fixture
def maintained(make_orchestrator, demo_script, walk):
    def build(script=None):
        orch = make_orchestrator(script or demo_script)
        orch.sandbox = LocalSandbox()
        return orch, walk(orch, P.MAINTENANCE)

    return build


def test_change_request_names_affected_artifacts_and_starts_in_requirements(maintained):
    orch, pid = maintained()
    result = orch.run_action(pid, P.MAINTENANCE, "change", {"request": "Tasks need a priority"})
    change = orch.store.get_artifact(pid, "change-1")
    assert change.content["kind"] == "change" and change.content["affected"] == ["REQ-001", "REQ-002"]
    touched = {a["id"] for a in change.content["impact"]["REQ-002"]}
    assert any(t.startswith("diagram-") for t in touched) and any(t.startswith("source-") for t in touched)
    assert any(t.startswith("test-") for t in touched)
    step = result.outcome.data["next_actions"][0]
    assert (step["phase"], step["action"]) == ("requirements", "revise") and "priority" in step["input"]["feedback"]
    assert change.covers == []  # a change request does not count as coverage
    # the analyst looked at the trace first
    tool_events = [e for e in orch.store.list_events(pid) if e.kind == "agent.tool_call"]
    assert any("trace_impact" in e.summary for e in tool_events)


def test_starting_the_change_makes_every_later_phase_out_of_date(maintained):
    orch, pid = maintained()
    result = orch.run_action(pid, P.MAINTENANCE, "change", {"request": "Tasks need a priority"})
    step = result.outcome.data["next_actions"][0]
    orch.run_action(pid, step["phase"], step["action"], step["input"])
    project = orch.project(pid)
    assert project.status(P.REQUIREMENTS) is S.DRAFT
    assert all(project.status(ph) is S.STALE for ph in list(P)[1:])
    with pytest.raises(PhaseLockedError):
        orch.run_action(pid, P.DESIGN, "generate", {})  # requirements must be approved again first


def test_unknown_ids_are_dropped_and_a_bug_goes_to_code(maintained, demo_script):
    script = copy.deepcopy(demo_script)
    script["impact_analyst"] = [
        {"kind": "bug", "summary": "Deleting task 2 deletes task 1.", "affected": ["REQ-004", "REQ-099"], "fix": "Compare numbers, not positions.", "steps": ["Code: fix delete."]}
    ]
    orch, pid = maintained(script)
    result = orch.run_action(pid, P.MAINTENANCE, "change", {"request": "delete removes the wrong task"})
    change = orch.store.get_artifact(pid, "change-1")
    assert change.content["affected"] == ["REQ-004"] and change.content["unknown"] == ["REQ-099"]
    assert change.content["phases"] == ["code", "tests", "deployment"]
    step = result.outcome.data["next_actions"][0]
    assert (step["phase"], step["action"], step["input"]) == ("codegen", "revise", {"feedback": "Compare numbers, not positions."})


def test_changes_are_numbered(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "one"})
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "two"})
    assert orch.store.get_artifact(pid, "change-2").content["request"] == "two"


def test_check_reports_everything_in_sync_after_the_happy_path(maintained):
    orch, pid = maintained()
    result = orch.run_action(pid, P.MAINTENANCE, "check", {})
    report = orch.store.get_artifact(pid, "consistency")
    assert report.content["in_sync"] is True
    assert report.content["verified"] == report.content["total"] == 5
    assert "Design and code agree." in result.outcome.reply
    assert result.outcome.data["next_actions"] == []
    assert not [c for c in orch.llm.calls if c.agent == "impact_analyst"]  # no model asked


def test_hand_edited_code_shows_drift_and_offers_both_directions(maintained):
    orch, pid = maintained()
    service = orch.store.get_artifact(pid, "source-todo-service-py")
    orch.update_artifact(pid, service.id, text=service.text + "\n\nclass Archive:\n    def restore(self):\n        pass\n")
    # editing code makes later phases stale; maintenance is locked until they are approved again
    for ph in (P.CODEGEN, P.TESTING, P.DEPLOYMENT):
        if ph is P.TESTING:
            orch.run_action(pid, ph, "run", {})
        if ph is P.DEPLOYMENT:
            orch.run_action(pid, ph, "check", {})
        orch.approve(pid, ph)
    result = orch.run_action(pid, P.MAINTENANCE, "check", {})
    report = orch.store.get_artifact(pid, "consistency")
    assert report.content["in_sync"] is False
    assert "Archive is in the code but not in the class diagram." in report.content["drift_lines"]
    assert report.content["hand_edited"] == ["todo/service.py"]
    labels = [(a["phase"], a["action"]) for a in result.outcome.data["next_actions"]]
    assert labels == [("refinement", "comment"), ("codegen", "revise")]


def test_check_needs_code(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = orch.create_project("Empty").id
    ctx = PhaseContext(project=orch.project(pid), phase=P.MAINTENANCE, store=ReadOnlyStore(orch.store), llm=orch.llm, renderer=orch.renderer)
    with pytest.raises(InvalidTransitionError):
        MODULE.run("check", MODULE.action("check").input_model(), ctx)


def test_trace_view_carries_test_results(maintained):
    orch, pid = maintained()
    view = orch.trace_view(pid)
    assert view.results == {f"REQ-00{i}": "passed" for i in range(1, 6)}
