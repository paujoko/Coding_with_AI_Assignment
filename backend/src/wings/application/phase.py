"""The contract every wing implements.

A phase module declares what it needs (`requires`), what the developer can ask
it to do (`actions`, each with a typed input model) and does the work in
`run`. It gets everything it may touch through `PhaseContext`; it never
imports adapters or other phases (enforced by tests/architecture).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from wings.domain.activity import Message
from wings.domain.artifacts import Artifact
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.project import Project
from wings.application.ports import ArtifactStore, DiagramRenderer, LLMClient


class NoInput(BaseModel):
    pass


class ActionSpec(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    label: str  # button text in the UI
    description: str
    input_model: type[BaseModel] = NoInput
    message_field: str | None = None  # input field that holds what the developer said (logged in the conversation)

    def public(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
            "message_field": self.message_field,
        }


class AgentInfo(BaseModel):
    name: str
    role: str
    tier: str


class ActionOutcome(BaseModel):
    status: PhaseStatus | None = None  # None: leave the phase status as it is (e.g. a discussion)
    reply: str | None = None  # what the agent says to the developer
    artifacts: list[Artifact] = Field(default_factory=list)  # new revisions to save
    data: dict[str, Any] = Field(default_factory=dict)  # extra results for the UI (coverage, questions ...)


LogFn = Callable[[str, str, dict[str, Any]], None]


@dataclass
class PhaseContext:
    project: Project
    phase: PhaseId
    store: ArtifactStore
    llm: LLMClient
    renderer: DiagramRenderer
    log: LogFn = field(default=lambda kind, summary, data: None)

    def artifacts(self, phase: PhaseId | None = None) -> list[Artifact]:
        return self.store.list_artifacts(self.project.id, phase)

    def messages(self, phase: PhaseId | None = None) -> list[Message]:
        return self.store.list_messages(self.project.id, phase or self.phase)


class PhaseModule(ABC):
    id: ClassVar[PhaseId]
    title: ClassVar[str]
    summary: ClassVar[str]
    requires: ClassVar[list[PhaseId]] = []
    implemented: ClassVar[bool] = True

    @property
    @abstractmethod
    def actions(self) -> list[ActionSpec]: ...

    @property
    def agents(self) -> list[AgentInfo]:
        return []

    def action(self, name: str) -> ActionSpec | None:
        return next((a for a in self.actions if a.name == name), None)

    @abstractmethod
    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome: ...

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        """The developer edited an artifact by hand. Override to validate and re-render (raise ValueError to reject)."""
        update: dict[str, Any] = {}
        if content is not None:
            update["content"] = content
        if text is not None:
            update["text"] = text
        return artifact.model_copy(update=update)

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id.value,
            "title": self.title,
            "summary": self.summary,
            "requires": [r.value for r in self.requires],
            "implemented": self.implemented,
            "actions": [a.public() for a in self.actions],
            "agents": [a.model_dump() for a in self.agents],
        }


class PlannedPhase(PhaseModule):
    """A wing that is registered in the pipeline but not built yet."""

    implemented: ClassVar[bool] = False

    @property
    def actions(self) -> list[ActionSpec]:
        return []

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        raise NotImplementedError(f"Phase '{self.id.value}' is planned but not implemented yet.")
