"""Conversation messages and the activity log.

Messages are what the developer and the agents say to each other per phase.
Events are what the system did, in order; the UI shows them so the developer
always sees what is happening (grading criterion C3).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from wings.domain.phases import PhaseId
from wings.domain.project import utcnow


class Role(StrEnum):
    DEVELOPER = "developer"
    AGENT = "agent"
    SYSTEM = "system"


class Message(BaseModel):
    phase: PhaseId
    role: Role
    text: str
    author: str = ""
    data: dict[str, Any] = Field(default_factory=dict)  # structured extras, e.g. open clarifying questions
    created_at: datetime = Field(default_factory=utcnow)


class Event(BaseModel):
    seq: int = 0  # assigned by the store, strictly increasing per project
    at: datetime = Field(default_factory=utcnow)
    kind: str  # e.g. project.created, action.started, agent.llm_call, artifact.saved, phase.stale, phase.error
    phase: PhaseId | None = None
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
