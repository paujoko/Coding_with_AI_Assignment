from typing import ClassVar

import pytest

from wings.application.phase import PlannedPhase
from wings.application.registry import PhaseRegistry, RegistryError
from wings.domain.errors import NotFoundError
from wings.domain.phases import PhaseId as P


def planned(pid: P, requires: list[P]) -> PlannedPhase:
    cls = type(f"Planned_{pid.value}", (PlannedPhase,), {"id": pid, "title": pid.value, "summary": "", "requires": requires})
    return cls()


def test_orders_and_reports_dependencies():
    reg = PhaseRegistry([planned(P.REQUIREMENTS, []), planned(P.DESIGN, [P.REQUIREMENTS])])
    assert [m.id for m in reg.ordered()] == [P.REQUIREMENTS, P.DESIGN]
    assert reg.dependencies() == {P.REQUIREMENTS: [], P.DESIGN: [P.REQUIREMENTS]}


def test_rejects_cycle():
    with pytest.raises(RegistryError, match="cycle"):
        PhaseRegistry([planned(P.REQUIREMENTS, [P.DESIGN]), planned(P.DESIGN, [P.REQUIREMENTS])])


def test_rejects_unknown_dependency():
    with pytest.raises(RegistryError, match="unregistered"):
        PhaseRegistry([planned(P.DESIGN, [P.REQUIREMENTS])])


def test_unknown_phase_is_not_found():
    reg = PhaseRegistry([planned(P.REQUIREMENTS, [])])
    with pytest.raises(NotFoundError):
        reg.get("nonsense")
    with pytest.raises(NotFoundError):
        reg.get(P.DESIGN)
