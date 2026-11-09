"""Design refinement wing (planned). Intended behaviour and next steps: README.md in this folder."""

from typing import ClassVar

from wings.application.phase import PlannedPhase
from wings.domain.phases import PhaseId


class RefinementPhase(PlannedPhase):
    id: ClassVar[PhaseId] = PhaseId.REFINEMENT
    title: ClassVar[str] = "Design refinement"
    summary: ClassVar[str] = "Interactive loop: comments on a diagram update all diagrams consistently; the system reviews its own design."
    requires: ClassVar[list[PhaseId]] = [PhaseId.DESIGN]


MODULE = RefinementPhase()
