"""Catch up: bring every out-of-date phase up to date, one phase per call, without a tracked change."""

import pytest

from wings.adapters.sandbox import LocalSandbox
from wings.domain.errors import ConflictError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S

PIPELINE = [P.REQUIREMENTS, P.DESIGN, P.REFINEMENT, P.CODEGEN, P.TESTING, P.DEPLOYMENT]


@pytest.fixture
def maintained(make_orchestrator, demo_script, walk):
    def build():
        orch = make_orchestrator(demo_script)
        orch.sandbox = LocalSandbox()
        return orch, walk(orch, P.MAINTENANCE)

    return build


def revise_requirements(orch, pid):
    """A new revision of the requirements: they are approved again, everything behind them is stale."""
    orch.run_action(pid, P.REQUIREMENTS, "revise", {"feedback": "Tasks need a priority"})
    orch.approve(pid, P.REQUIREMENTS)


def stale(orch, pid):
    return [p for p in PIPELINE if orch.project(pid).status(p) is S.STALE]


def spy(orch, phase, monkeypatch):
    """Record the reason each refresh step of `phase` is asked with."""
    seen = []
    module = orch.registry.get(phase)
    original = module.refresh_step
    monkeypatch.setattr(module, "refresh_step", lambda reason, artifacts: seen.append(reason) or original(reason, artifacts))
    return seen


def test_nothing_stale_means_everything_is_up_to_date(maintained):
    orch, pid = maintained()
    result = orch.catch_up(pid)
    assert (result.done, result.ran, result.remaining, result.approved) == (True, [], [], None)
    assert result.stopped_reason == "Everything is up to date."


def test_catch_up_handles_one_phase_per_call_and_approves_it_on_the_developers_behalf(maintained):
    orch, pid = maintained()
    revise_requirements(orch, pid)
    assert stale(orch, pid) == PIPELINE[1:]
    first = orch.catch_up(pid)
    assert [(r.phase, r.action, r.status) for r in first.ran] == [(P.DESIGN, "revise", S.DRAFT)]
    assert first.approved is P.DESIGN and first.stopped_reason is None and not first.done
    assert first.remaining == PIPELINE[2:]
    assert first.project.status(P.DESIGN) is S.APPROVED and first.project.status(P.CODEGEN) is S.STALE
    [event] = [e for e in orch.store.list_events(pid) if e.kind == "phase.approved" and e.data.get("catch_up")]
    assert event.data["on_behalf"] is True and event.phase is P.DESIGN and "at the developer's request" in event.summary


def test_catching_up_all_the_way_updates_the_code_and_leaves_nothing_stale(maintained):
    orch, pid = maintained()
    revise_requirements(orch, pid)
    old = orch.store.get_artifact(pid, "source-todo-service-py").revision
    calls = []
    for _ in range(8):
        result = orch.catch_up(pid)
        calls.append(result)
        if result.done or result.stopped_reason:
            break
    assert [c.approved for c in calls] == PIPELINE[1:]
    assert calls[-1].done and calls[-1].stopped_reason is None and calls[-1].remaining == []
    assert stale(orch, pid) == []
    assert all(orch.project(pid).status(p) is S.APPROVED for p in PIPELINE)
    assert orch.store.get_artifact(pid, "source-todo-service-py").revision > old  # regenerated, not just approved
    assert orch.catch_up(pid).stopped_reason == "Everything is up to date."


def test_without_approval_it_stops_for_review(maintained):
    orch, pid = maintained()
    revise_requirements(orch, pid)
    result = orch.catch_up(pid, approve=False)
    assert result.approved is None and result.project.status(P.DESIGN) is S.DRAFT
    assert "Design is ready for review" in result.stopped_reason and not result.done
    assert result.remaining == PIPELINE[2:]
    blocked = orch.catch_up(pid)  # Design is a draft now: the stale phases behind it cannot run before it is approved
    assert blocked.ran == [] and "Design" in blocked.stopped_reason and "approved" in blocked.stopped_reason


def test_a_failed_action_stops_it_and_saves_nothing(maintained):
    orch, pid = maintained()
    revise_requirements(orch, pid)
    orch.llm._script = {k: v for k, v in orch.llm._script.items() if not k.startswith("architect")}
    failed = orch.catch_up(pid)
    assert failed.ran == [] and failed.approved is None and "did not finish" in failed.stopped_reason
    assert failed.project.status(P.DESIGN) is S.STALE and failed.remaining == PIPELINE[1:]


def test_a_wing_without_a_refresh_step_is_named_and_never_looped_on(maintained, monkeypatch):
    orch, pid = maintained()
    revise_requirements(orch, pid)
    monkeypatch.setattr(orch.registry.get(P.DESIGN), "refresh_step", lambda reason, artifacts: [])
    result = orch.catch_up(pid)
    assert result.ran == [] and result.approved is None
    assert "Design" in result.stopped_reason and "by hand" in result.stopped_reason
    assert result.remaining == PIPELINE[1:] and not result.done


def test_the_wing_is_told_what_changed_upstream(maintained, monkeypatch):
    orch, pid = maintained()
    revise_requirements(orch, pid)
    seen = spy(orch, P.DESIGN, monkeypatch)
    orch.catch_up(pid)
    assert "Requirements changed" in seen[0] and "Design is out of date" in seen[0]


def test_a_hand_edit_is_named_in_the_reason(maintained, monkeypatch):
    orch, pid = maintained()
    code = orch.store.get_artifact(pid, "source-todo-service-py")
    orch.update_artifact(pid, code.id, text=(code.text or "") + "\n# edited by hand\n")
    assert orch.project(pid).status(P.CODEGEN) is S.DRAFT and orch.project(pid).status(P.TESTING) is S.STALE
    seen = spy(orch, P.TESTING, monkeypatch)
    orch.approve(pid, P.CODEGEN)
    orch.catch_up(pid, approve=False)
    assert "Code generation changed" in seen[0] and "edited by hand" in seen[0] and "service.py" in seen[0]


def test_an_open_change_is_carried_through_the_same_way_and_closed_with_the_check(maintained):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "Tasks need a priority"})
    orch.advance_change(pid, 1)  # requirements: revised and approved, the rest is stale
    results = []
    for _ in range(8):
        result = orch.catch_up(pid)
        results.append(result)
        if result.done or result.stopped_reason:
            break
    assert [r.approved for r in results] == PIPELINE[1:] and results[-1].done
    [change] = orch.changes(pid)
    assert change.state == "complete" and all(p.state == "done" for p in change.progress.phases)
    assert orch.open_change(pid) is None
    assert any(e.kind == "phase.approved" and e.data.get("change") == 1 and e.data.get("catch_up") for e in orch.store.list_events(pid))
    checks = [a for a in orch.store.list_artifacts(pid) if a.id == "consistency"]
    assert checks and checks[-1].created_at >= change.completed_at  # Maintenance's consistency check ran
    assert orch.project(pid).status(P.MAINTENANCE) is S.DRAFT


def test_the_change_request_text_reaches_a_phase_even_when_the_change_does_not_plan_it(maintained, monkeypatch):
    orch, pid = maintained()
    orch.run_action(pid, P.MAINTENANCE, "change", {"request": "Tasks need a priority"})
    orch.advance_change(pid, 1)
    seen = spy(orch, P.DESIGN, monkeypatch)
    orch.catch_up(pid, approve=False)
    assert "Tasks need a priority" in seen[0]  # advance_change's reason: the change request in words


def test_a_second_action_while_an_agent_works_is_refused(maintained):
    orch, pid = maintained()
    revise_requirements(orch, pid)
    with orch._claim(pid, P.DESIGN, "generate", "Generate"), pytest.raises(ConflictError):
        orch.catch_up(pid)
