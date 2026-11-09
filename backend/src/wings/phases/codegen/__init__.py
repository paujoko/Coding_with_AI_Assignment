"""Code generation wing (planned). Intended behaviour and next steps: README.md in this folder."""

from typing import ClassVar

from wings.application.phase import PlannedPhase
from wings.domain.phases import PhaseId


class CodegenPhase(PlannedPhase):
    id: ClassVar[PhaseId] = PhaseId.CODEGEN
    title: ClassVar[str] = "Code generation"
    summary: ClassVar[str] = "Generates code from the approved design, so classes and calls mirror the diagrams."
    requires: ClassVar[list[PhaseId]] = [PhaseId.REFINEMENT]


MODULE = CodegenPhase()
