"""Deployment wing (planned). Intended behaviour and next steps: README.md in this folder."""

from typing import ClassVar

from wings.application.phase import PlannedPhase
from wings.domain.phases import PhaseId


class DeploymentPhase(PlannedPhase):
    id: ClassVar[PhaseId] = PhaseId.DEPLOYMENT
    title: ClassVar[str] = "Deployment"
    summary: ClassVar[str] = "Generates and checks deployment artifacts (Dockerfile, compose file or start script)."
    requires: ClassVar[list[PhaseId]] = [PhaseId.TESTING]


MODULE = DeploymentPhase()
