"""Ports: the interfaces the core needs from the outside world.

Adapters in `wings.adapters` implement them; `wings.bootstrap` picks which.
Shaped so each port can later be exposed as (or backed by) an MCP server.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from wings.domain.activity import Event, Message
from wings.domain.artifacts import Artifact
from wings.domain.phases import PhaseId
from wings.domain.project import Project

Tier = Literal["small", "mid", "frontier"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    agent: str  # which agent is calling; used for logging, model choice and mock scripts
    system: str
    messages: list[ChatTurn]
    tier: Tier = "mid"
    json_mode: bool = True


class LLMReply(BaseModel):
    text: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = None


class LLMError(Exception):
    """Transport or provider failure (network, auth, rate limit)."""


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMReply: ...


class ArtifactStore(Protocol):
    def save_project(self, project: Project) -> None: ...
    def load_project(self, project_id: str) -> Project: ...  # raises NotFoundError
    def list_projects(self) -> list[Project]: ...
    def project_exists(self, project_id: str) -> bool: ...

    def save_artifact(self, project_id: str, artifact: Artifact) -> Artifact: ...  # assigns the next revision
    def get_artifact(self, project_id: str, artifact_id: str) -> Artifact: ...  # latest revision; raises NotFoundError
    def list_artifacts(self, project_id: str, phase: PhaseId | None = None) -> list[Artifact]: ...
    def artifact_history(self, project_id: str, artifact_id: str) -> list[Artifact]: ...

    def append_message(self, project_id: str, message: Message) -> None: ...
    def list_messages(self, project_id: str, phase: PhaseId | None = None) -> list[Message]: ...

    def append_event(self, project_id: str, event: Event) -> Event: ...  # assigns seq
    def list_events(self, project_id: str, after: int = 0) -> list[Event]: ...


class DiagramRenderer(Protocol):
    @property
    def available(self) -> bool: ...

    def render_svg(self, source: str) -> str | None: ...  # None when rendering is not possible
