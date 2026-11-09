"""Ports: the interfaces the core needs from the outside world.

Adapters in `wings.adapters` implement them; `wings.bootstrap` picks which.
Shaped so each port can later be exposed as (or backed by) an MCP server.
"""

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from wings.domain.activity import Event, Message
from wings.domain.artifacts import Artifact
from wings.domain.attachments import Attachment
from wings.domain.phases import PhaseId
from wings.domain.project import Project

Tier = Literal["small", "mid", "frontier"]


class ToolCall(BaseModel):
    """The model asks to run a tool."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolSpec(BaseModel):
    """A tool offered to the model: name, what it does, JSON schema of its arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)  # assistant turns that called tools
    tool_call_id: str | None = None  # tool turns: which call this is the result of


class LLMRequest(BaseModel):
    agent: str  # which agent is calling; used for logging, model choice and mock scripts
    system: str
    messages: list[ChatTurn]
    tier: Tier = "mid"
    json_mode: bool = True
    tools: list[ToolSpec] = Field(default_factory=list)


class LLMReply(BaseModel):
    text: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)  # set when the model wants tools run first


class LLMError(Exception):
    """Transport or provider failure (network, auth, rate limit)."""


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMReply: ...


class ArtifactReader(Protocol):
    """What a wing may read. Wings never write: they return artifacts and the orchestrator saves them."""

    def get_artifact(self, project_id: str, artifact_id: str) -> Artifact: ...  # latest revision; raises NotFoundError
    def list_artifacts(self, project_id: str, phase: PhaseId | None = None) -> list[Artifact]: ...
    def artifact_history(self, project_id: str, artifact_id: str) -> list[Artifact]: ...
    def list_messages(self, project_id: str, phase: PhaseId | None = None) -> list[Message]: ...
    def list_attachments(self, project_id: str) -> list[Attachment]: ...
    def get_attachment(self, project_id: str, attachment_id: str) -> Attachment: ...  # raises NotFoundError


class ArtifactStore(ArtifactReader, Protocol):
    def save_project(self, project: Project) -> None: ...  # raises ConflictError if saved by someone else meanwhile
    def load_project(self, project_id: str) -> Project: ...  # raises NotFoundError
    def list_projects(self) -> list[Project]: ...
    def project_exists(self, project_id: str) -> bool: ...

    def check_artifact(self, project_id: str, artifact: Artifact) -> None: ...  # ValueError if id or path unsafe
    def save_artifact(self, project_id: str, artifact: Artifact) -> Artifact: ...  # assigns the next revision

    def append_message(self, project_id: str, message: Message) -> None: ...
    def save_attachment(self, project_id: str, attachment: Attachment, data: bytes) -> Attachment: ...  # assigns the id

    def append_event(self, project_id: str, event: Event) -> Event: ...  # assigns seq
    def list_events(self, project_id: str, after: int = 0) -> list[Event]: ...


class ReadOnlyStore:
    """Narrowed view handed to wings (enforces the rule above at runtime)."""

    def __init__(self, store: ArtifactStore):
        self._s = store

    def get_artifact(self, project_id: str, artifact_id: str) -> Artifact:
        return self._s.get_artifact(project_id, artifact_id)

    def list_artifacts(self, project_id: str, phase: PhaseId | None = None) -> list[Artifact]:
        return self._s.list_artifacts(project_id, phase)

    def artifact_history(self, project_id: str, artifact_id: str) -> list[Artifact]:
        return self._s.artifact_history(project_id, artifact_id)

    def list_messages(self, project_id: str, phase: PhaseId | None = None) -> list[Message]:
        return self._s.list_messages(project_id, phase)

    def list_attachments(self, project_id: str) -> list[Attachment]:
        return self._s.list_attachments(project_id)

    def get_attachment(self, project_id: str, attachment_id: str) -> Attachment:
        return self._s.get_attachment(project_id, attachment_id)


class TextExtractor(Protocol):
    """Turns an uploaded file into plain text for the agents."""

    def extract(self, name: str, media_type: str, data: bytes) -> str: ...  # InvalidInputError if not readable


class LLMSettingsService(Protocol):
    """Model provider settings as the UI edits them. Implemented in the composition root (it builds adapters)."""

    def view(self) -> dict[str, Any]: ...  # never contains an API key, only a hint
    def update(self, provider: str, api_key: str | None, models: dict[str, str] | None) -> dict[str, Any]: ...
    def test(self) -> dict[str, Any]: ...


class DiagramSettingsService(Protocol):
    """How diagrams are drawn, as the UI sets it up. Implemented in the composition root."""

    def view(self) -> dict[str, Any]: ...
    def use_public_server(self, enabled: bool) -> dict[str, Any]: ...
    def download_jar(self) -> dict[str, Any]: ...


class DiagramRenderer(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def mode(self) -> str | None: ...  # "jar", "server" or None

    def render_svg(self, source: str) -> str | None: ...  # None when rendering is not possible
    def check(self, source: str) -> str | None: ...  # a syntax error with its line, None if fine or not checkable
