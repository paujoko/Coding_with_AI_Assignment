"""Artifacts: everything a phase produces (requirements, diagrams, later code, tests, deployment files).

Artifacts are versioned: every save creates a new revision, older revisions stay
in the store. `covers` holds the trace IDs (REQ-001 ...) an artifact implements;
it is what lets later wings answer "which requirement does this belong to?".
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from wings.domain.phases import PhaseId
from wings.domain.project import utcnow


class ArtifactKind(StrEnum):
    REQUIREMENTS = "requirements"
    DIAGRAM = "diagram"
    # Planned wings will add: SOURCE_FILE, TEST_SUITE, TEST_REPORT, DEPLOYMENT, CHANGE_REQUEST.


DEVELOPER = "developer"


def agent_author(agent: str) -> str:
    return f"agent:{agent}"


class Artifact(BaseModel):
    id: str
    kind: ArtifactKind
    phase: PhaseId
    title: str
    revision: int = 0  # assigned by the store on save
    content: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None  # human-readable rendering (markdown, PlantUML source ...)
    path: str | None = None  # where `text` is materialized inside the workspace
    defines: list[str] = Field(default_factory=list)  # trace IDs introduced here (REQ-001 in the requirements)
    covers: list[str] = Field(default_factory=list)  # trace IDs this artifact implements
    author: str = DEVELOPER
    retired: bool = False  # no longer part of the current output; history is kept
    created_at: datetime = Field(default_factory=utcnow)
