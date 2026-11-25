"""Conversation messages and the activity log.

Messages are what the developer and the agents say to each other per phase,
and the developer's decisions (ADR 0022): a choice, a button, an edit by hand,
each recorded as one line in the conversation of the step it belongs to.
Events are what the system did, in order; the UI shows them so the developer
always sees what is happening (grading criterion C3).

Three kinds of message, told apart by role and `data`:
- the developer's words: role developer, author developer (as always);
- a decision of the developer: role developer, author developer, `data.decision`
  ({"action": ..., details}); the text is one readable line ("Ran the tests");
- something Wings did on the developer's behalf (carrying a change, catching up):
  role system, author `wings`, `data.on_behalf` ({"change": n} or {"catch_up": true}).
  With `data.decision` it is a line ("Accepted on your behalf"); without, its text
  is the instruction Wings sent to the agent.
Decisions are never sent to a model; instructions Wings wrote are (`for_agents`).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from wings.domain.artifacts import DEVELOPER
from wings.domain.phases import PhaseId
from wings.domain.project import utcnow

WINGS = "wings"  # author of what Wings wrote or did on the developer's behalf


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

    @property
    def is_decision(self) -> bool:
        """A decision line (a choice, a button, an edit): shown in the conversation, never sent to a model."""
        return bool(self.data.get("decision"))

    @property
    def on_behalf(self) -> bool:
        """Written or done by Wings on the developer's behalf, never by the developer."""
        return bool(self.data.get("on_behalf"))


def decision(phase: PhaseId, text: str, action: str, details: dict[str, Any] | None = None, on_behalf: dict[str, Any] | None = None) -> Message:
    """A decision line. `on_behalf` set: Wings took it while carrying a change or catching up."""
    data: dict[str, Any] = {"decision": {"action": action} | (details or {})}
    if on_behalf:
        return Message(phase=phase, role=Role.SYSTEM, text=text, author=WINGS, data=data | {"on_behalf": on_behalf})
    return Message(phase=phase, role=Role.DEVELOPER, text=text, author=DEVELOPER, data=data)


def instruction(phase: PhaseId, text: str, action: str, label: str, on_behalf: dict[str, Any]) -> Message:
    """Words Wings wrote to an agent on the developer's behalf (e.g. "The requirements changed. Update every diagram
    ..."). Sent to the model like the developer's words, but never shown or stored as theirs."""
    return Message(phase=phase, role=Role.SYSTEM, text=text, author=WINGS, data={"on_behalf": on_behalf, "action": action, "label": label})


def for_agents(messages: list[Message]) -> list[Message]:
    """The messages an agent reads: the developer's words, the agents' replies and Wings' instructions.
    Decision lines stay out; the agents learn the result of a decision from the artifacts."""
    return [m for m in messages if not m.is_decision and (m.role is not Role.SYSTEM or m.on_behalf)]


class Event(BaseModel):
    seq: int = 0  # assigned by the store, strictly increasing per project
    at: datetime = Field(default_factory=utcnow)
    kind: str  # e.g. project.created, action.started, agent.llm_call, artifact.saved, phase.stale, phase.error
    phase: PhaseId | None = None
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
