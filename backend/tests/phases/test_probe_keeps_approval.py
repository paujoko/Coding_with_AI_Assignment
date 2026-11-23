"""A computed report about a phase (injected bugs) must not reopen the phase or age later ones."""

from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus

from wings.adapters.sandbox import LocalSandbox
from wings.application.phase import ActionOutcome


def test_an_outcome_changes_its_phase_unless_it_says_otherwise():
    assert ActionOutcome().changes_phase is True
    assert ActionOutcome(changes_phase=False).changes_phase is False


def test_injecting_bugs_after_approval_keeps_testing_approved(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    orch.sandbox = LocalSandbox()
    pid = walk(orch, P.DEPLOYMENT)
    assert orch.project(pid).status(P.TESTING) is PhaseStatus.APPROVED
    deployment_before = orch.project(pid).status(P.DEPLOYMENT)

    result = orch.run_action(pid, P.TESTING, "probe", {"limit": 2})

    assert result.stale == []
    project = orch.project(pid)
    assert project.status(P.TESTING) is PhaseStatus.APPROVED
    assert project.status(P.DEPLOYMENT) is deployment_before
    assert any(a.id == "test-strength" for a in orch.store.list_artifacts(pid))
