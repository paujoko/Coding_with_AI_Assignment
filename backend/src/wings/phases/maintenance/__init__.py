"""Maintenance wing (planned). Intended behaviour and next steps: README.md in this folder."""

from typing import ClassVar

from wings.application.phase import PlannedPhase
from wings.domain.phases import PhaseId


class MaintenancePhase(PlannedPhase):
    id: ClassVar[PhaseId] = PhaseId.MAINTENANCE
    title: ClassVar[str] = "Maintenance"
    summary: ClassVar[str] = "Propagates change requests through all artifacts and detects drift between code and diagrams."
    requires: ClassVar[list[PhaseId]] = [PhaseId.DEPLOYMENT]


MODULE = MaintenancePhase()
