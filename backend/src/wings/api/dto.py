"""Request and response shapes of the HTTP API (kept apart from domain models on purpose)."""

from typing import Any

from pydantic import BaseModel, Field

from wings.application.orchestrator import ActionResult
from wings.application.registry import PhaseRegistry
from wings.domain.artifacts import Artifact
from wings.domain.project import Project


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ActionRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


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
