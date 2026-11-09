import pytest

from wings.domain.errors import InvalidTransitionError, PhaseLockedError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S
from wings.domain.project import Project, slugify

CHAIN = {
    P.REQUIREMENTS: [],
    P.DESIGN: [P.REQUIREMENTS],
    P.REFINEMENT: [P.DESIGN],
    P.CODEGEN: [P.REFINEMENT],
    P.TESTING: [P.CODEGEN],
    P.DEPLOYMENT: [P.TESTING],
    P.MAINTENANCE: [P.DEPLOYMENT],
}


def new() -> Project:
    return Project.new("Todo App", CHAIN)


def test_new_project_only_first_phase_ready():
    p = new()
    assert p.status(P.REQUIREMENTS) is S.READY
    assert all(p.status(ph) is S.LOCKED for ph in CHAIN if ph is not P.REQUIREMENTS)
    assert p.id == "todo-app"


def test_approve_unlocks_dependants():
    p = new()
    p.set_status(P.REQUIREMENTS, S.DRAFT)
    p.approve(P.REQUIREMENTS)
    assert p.status(P.REQUIREMENTS) is S.APPROVED
    assert p.status(P.DESIGN) is S.READY
    assert p.status(P.REFINEMENT) is S.LOCKED


def test_approve_without_output_is_rejected():
    p = new()
    with pytest.raises(InvalidTransitionError):
        p.approve(P.REQUIREMENTS)


def test_running_locked_phase_is_rejected():
    p = new()
    assert not p.can_run(P.DESIGN)
    with pytest.raises(PhaseLockedError):
        p.ensure_can_run(P.DESIGN)


def test_change_marks_downstream_stale_but_keeps_locked():
    p = new()
    p.set_status(P.REQUIREMENTS, S.DRAFT)
    p.approve(P.REQUIREMENTS)
    p.set_status(P.DESIGN, S.DRAFT)
    stale = p.mark_changed(P.REQUIREMENTS)
    assert stale == [P.DESIGN]
    assert p.status(P.DESIGN) is S.STALE
    assert p.status(P.REFINEMENT) is S.LOCKED
    # The changed phase itself goes back to draft: it needs approval again.
    assert p.status(P.REQUIREMENTS) is S.DRAFT


def test_staleness_is_transitive():
    p = new()
    for ph in (P.REQUIREMENTS, P.DESIGN, P.REFINEMENT):
        p.set_status(ph, S.DRAFT)
        p.approve(ph)
    stale = p.mark_changed(P.REQUIREMENTS)
    assert stale == [P.DESIGN, P.REFINEMENT]
    # A stale phase stops being a valid input: codegen is locked again.
    assert p.status(P.CODEGEN) is S.LOCKED


def test_stale_phase_can_run_again_once_inputs_are_approved():
    p = new()
    p.set_status(P.REQUIREMENTS, S.DRAFT)
    p.approve(P.REQUIREMENTS)
    p.set_status(P.DESIGN, S.DRAFT)
    p.mark_changed(P.REQUIREMENTS)
    assert not p.can_run(P.DESIGN)
    p.approve(P.REQUIREMENTS)
    assert p.can_run(P.DESIGN)
    assert p.status(P.DESIGN) is S.STALE


def test_gate_is_transitive():
    # Review finding 5: reopening requirements must also stop refinement, whose design input is still approved.
    p = new()
    for ph in (P.REQUIREMENTS, P.DESIGN):
        p.set_status(ph, S.DRAFT)
        p.approve(ph)
    assert p.can_run(P.REFINEMENT)
    p.reopen(P.REQUIREMENTS)
    assert not p.can_run(P.REFINEMENT)
    assert p.status(P.REFINEMENT) is S.LOCKED


def test_upstream_change_resets_open_questions_instead_of_staling_them():
    # Review finding 5: a phase that only asked questions has no output to approve.
    p = new()
    p.set_status(P.REQUIREMENTS, S.DRAFT)
    p.approve(P.REQUIREMENTS)
    p.set_status(P.DESIGN, S.NEEDS_INPUT)
    assert p.mark_changed(P.REQUIREMENTS) == []
    assert p.status(P.DESIGN) is S.LOCKED
    p.approve(P.REQUIREMENTS)
    assert p.status(P.DESIGN) is S.READY


def test_reopen_approved_phase():
    p = new()
    p.set_status(P.REQUIREMENTS, S.DRAFT)
    p.approve(P.REQUIREMENTS)
    p.reopen(P.REQUIREMENTS)
    assert p.status(P.REQUIREMENTS) is S.DRAFT
    assert p.status(P.DESIGN) is S.LOCKED


@pytest.mark.parametrize(
    "name, slug",
    [("Büro Buchung 2", "buero-buchung-2"), ("  Todo!! App ", "todo-app"), ("Straße", "strasse"), ("???", "project")],
)
def test_slugify(name, slug):
    assert slugify(name) == slug


def test_stale_phase_remembers_which_phase_changed():
    p = new()
    p.set_status(P.REQUIREMENTS, S.DRAFT)
    p.approve(P.REQUIREMENTS)
    p.set_status(P.DESIGN, S.DRAFT)
    p.approve(P.DESIGN)
    p.set_status(P.REFINEMENT, S.DRAFT)
    p.mark_changed(P.REQUIREMENTS)
    assert p.phases[P.DESIGN].stale_cause is P.REQUIREMENTS
    assert p.phases[P.REFINEMENT].stale_cause is P.REQUIREMENTS
    assert p.phases[P.REQUIREMENTS].stale_cause is None
    # Leaving the stale state clears the cause.
    p.approve(P.REQUIREMENTS)
    p.mark_changed(P.DESIGN)
    assert p.status(P.DESIGN) is S.DRAFT and p.phases[P.DESIGN].stale_cause is None
    assert p.phases[P.REFINEMENT].stale_cause is P.REQUIREMENTS
