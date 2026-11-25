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
    # Assistant turns: the provider's own content blocks of that reply, sent back unchanged by the adapter
    # that made them (Claude's thinking blocks must accompany its tool calls). Other adapters ignore it.
    provider_content: list[dict[str, Any]] | None = None


class LLMRequest(BaseModel):
    agent: str  # which agent is calling; used for logging, model choice and mock scripts
    system: str
    messages: list[ChatTurn]
    tier: Tier = "mid"
    json_mode: bool = True  # ask for JSON; adapters whose endpoint has no JSON mode rely on the prompt and validation
    tools: list[ToolSpec] = Field(default_factory=list)
    # "none": the tools stay defined but may not be called (the last round of call_structured).
    tool_choice: Literal["auto", "none"] = "auto"


class LLMReply(BaseModel):
    text: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float | None = None  # None: unknown (the provider reports none and no price is known), never 0
    tool_calls: list[ToolCall] = Field(default_factory=list)  # set when the model wants tools run first
    provider_content: list[dict[str, Any]] | None = None  # see ChatTurn.provider_content


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
    def delete_project(self, project_id: str) -> None: ...  # raises NotFoundError; never touches the developer's folder

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
    def update(
        self, provider: str, api_key: str | None, models: dict[str, str] | None, efforts: dict[str, str] | None = None
    ) -> dict[str, Any]: ...
    def test(self) -> dict[str, Any]: ...


class ProcessResult(BaseModel):
    exit_code: int
    output: str  # stdout and stderr, the end of it if long
    seconds: float = 0.0
    collected: dict[str, str] = Field(default_factory=dict)  # files read back from the run folder (e.g. a JUnit report)
    timed_out: bool = False
    not_found: bool = False  # the program could not be found or started (e.g. no node installed)


class Sandbox(Protocol):
    """Runs a program on a set of files in an isolated folder. "{python}" in argv is the interpreter Wings
    runs on, "{node}" the node on the PATH (ADR 0020); a program that is not there gives `not_found`.
    Used to run generated tests (P5) and to smoke-test the deployment (P6). Never raises for a failing program."""

    def run(
        self, files: dict[str, str], argv: list[str], timeout: float = 60.0, collect: list[str] | None = None, stdin: str | None = None
    ) -> ProcessResult:
        """`stdin`: text the program reads as standard input (interactive programs); None gives it none."""
        ...


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


class ProjectFolder(Protocol):
    """The developer's output folder on their computer (ADR 0015). `path` is the folder's absolute path;
    `rel` a file inside it with forward slashes. What to write and what counts as a hand edit is decided
    in `domain/sync.py`; the adapter only reads and writes, and refuses anything outside the folder."""

    def problem(self, path: str) -> str | None: ...  # why this folder cannot be used; None if fine. Changes nothing.
    def prepare(self, path: str) -> None: ...  # create it if missing; InvalidInputError if it cannot be written
    def default_path(self, name: str) -> str | None: ...  # <projects dir>/<name>; None when no projects dir is configured. Changes nothing.
    def same(self, a: str, b: str) -> bool: ...  # two spellings of one folder (case, slashes, a trailing separator)
    def is_empty(self, path: str) -> bool: ...  # missing, or nothing in it but a fresh .git; binary and big files count as content
    def exists(self, path: str) -> bool: ...
    def read_files(self, path: str) -> dict[str, str]: ...  # every text file, ignored folders and binary files skipped
    def write_file(self, path: str, rel: str, text: str) -> None: ...
    def delete_file(self, path: str, rel: str) -> None: ...  # also removes folders it leaves empty


class FolderPicker(Protocol):
    """The operating system's own "choose a folder" dialog, opened on the computer the backend runs on
    (a browser never tells a page the full path of a folder). Wings runs locally, so that is the developer's
    computer. Returns the chosen absolute path, None if the developer cancelled; InvalidInputError if no
    dialog can be shown there (then the path is typed)."""

    def pick(self, start: str | None = None, title: str = "Choose a folder") -> str | None: ...
