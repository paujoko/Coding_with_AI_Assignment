"""Request and response shapes of the HTTP API (kept apart from domain models on purpose)."""

import base64
import binascii
from typing import Any

from pydantic import BaseModel, Field

from wings.application.orchestrator import ActionResult
from wings.application.registry import PhaseRegistry
from wings.domain.artifacts import Artifact
from wings.domain.attachments import Attachment
from wings.domain.errors import InvalidInputError
from wings.domain.project import Project


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ActionRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)
    attachments: list[str] = Field(default_factory=list)  # ids of uploaded documents this message refers to


class DiagramSettingsUpdate(BaseModel):
    public_server: bool


class LLMSettingsUpdate(BaseModel):
    provider: str
    api_key: str | None = Field(default=None, max_length=400)  # empty or missing: keep the saved key
    models: dict[str, str] | None = None


class AttachmentUpload(BaseModel):
    """JSON upload (base64) keeps the API free of multipart handling; files are small (5 MB at most)."""

    name: str = Field(min_length=1, max_length=200)
    media_type: str = ""
    content_base64: str

    def data(self) -> bytes:
        try:
            return base64.b64decode(self.content_base64, validate=True)
        except (binascii.Error, ValueError) as err:
            raise InvalidInputError("The file content is not valid base64.") from err


class ArtifactUpdate(BaseModel):
    content: dict[str, Any] | None = None
    text: str | None = None


def project_view(project: Project, registry: PhaseRegistry) -> dict[str, Any]:
    phases = []
    for module in registry.ordered():
        state = project.phases[module.id]
        phases.append(
            {
                "id": module.id.value,
                "title": module.title,
                "status": state.status.value,
                "requires": [r.value for r in state.requires],
                "implemented": module.implemented,
                "can_run": module.implemented and project.can_run(module.id),
                "stale_cause": state.stale_cause.value if state.stale_cause else None,
                "updated_at": state.updated_at.isoformat(),
            }
        )
    return {"id": project.id, "name": project.name, "created_at": project.created_at.isoformat(), "phases": phases}


def artifact_view(a: Artifact) -> dict[str, Any]:
    return a.model_dump(mode="json")


def action_view(result: ActionResult, registry: PhaseRegistry) -> dict[str, Any]:
    return {
        "project": project_view(result.project, registry),
        "reply": result.outcome.reply,
        "artifacts": [artifact_view(a) for a in result.outcome.artifacts],
        "data": result.outcome.data,
        "stale": [s.value for s in result.stale],
    }


def attachment_view(a: Attachment) -> dict[str, Any]:
    """Without the text (it can be long); GET /attachments/{id} adds it."""
    return a.model_dump(mode="json", exclude={"text"}) | {"chars": len(a.text)}
