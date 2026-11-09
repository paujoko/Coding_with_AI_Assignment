"""Testing wing (planned). Intended behaviour and next steps: README.md in this folder."""

from typing import ClassVar

from wings.application.phase import PlannedPhase
from wings.domain.phases import PhaseId


class TestingPhase(PlannedPhase):
    id: ClassVar[PhaseId] = PhaseId.TESTING
    title: ClassVar[str] = "Testing"
    summary: ClassVar[str] = "Derives tests from requirements and design, runs them, explains failures and proposes fixes."
    requires: ClassVar[list[PhaseId]] = [PhaseId.CODEGEN]


MODULE = TestingPhase()
