"""Orchestrator: the manager agent's deterministic half.

It owns the rules that must not depend on an LLM: which phase may run, what an
approval unlocks, what becomes stale after a change, and the activity log.
Phase modules do the work; the orchestrator calls them and records everything.
"""

from typing import Any

from pydantic import BaseModel, Field

from wings.application.phase import ActionOutcome, PhaseContext
from wings.application.ports import ArtifactStore, DiagramRenderer, LLMClient, LLMError
from wings.application.registry import PhaseRegistry
from wings.application.structured import LLMOutputError
from wings.domain.activity import Event, Message, Role
from wings.domain.artifacts import DEVELOPER, Artifact
from wings.domain.errors import InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId
from wings.domain.project import Project, slugify, utcnow
from wings.domain.trace import CoverageReport, requirement_coverage


class ActionFailedError(Exception):
    """The phase could not finish (LLM unreachable, unusable output). Nothing was saved."""


class ActionResult(BaseModel):
    project: Project
    outcome: ActionOutcome
    stale: list[PhaseId] = Field(default_factory=list)


class Orchestrator:
    def __init__(self, registry: PhaseRegistry, store: ArtifactStore, llm: LLMClient, renderer: DiagramRenderer):
        self.registry = registry
        self.store = store
        self.llm = llm
        self.renderer = renderer

    # Projects

    def create_project(self, name: str) -> Project:
        base = slugify(name)
        pid, n = base, 1
        while self.store.project_exists(pid):
            n += 1
            pid = f"{base}-{n}"
        project = Project.new(name.strip() or pid, self.registry.dependencies(), project_id=pid)
        self.store.save_project(project)
        self._event(pid, "project.created", None, f"Project '{project.name}' created")
        return project

    def project(self, project_id: str) -> Project:
        return self.store.load_project(project_id)

    def list_projects(self) -> list[Project]:
        return self.store.list_projects()

    # Phase actions

    def run_action(self, project_id: str, phase: PhaseId | str, action: str, payload: dict[str, Any]) -> ActionResult:
        project = self.project(project_id)
        module = self.registry.get(phase)
        if not module.implemented:
            raise InvalidTransitionError(f"Phase '{module.id.value}' is planned but not implemented yet.")
        spec = module.action(action)
        if spec is None:
            raise NotFoundError(f"Phase '{module.id.value}' has no action '{action}'.")
        project.ensure_can_run(module.id)
        params = spec.input_model.model_validate(payload)  # pydantic.ValidationError is a ValueError

        pid, ph = project.id, module.id
        if spec.message_field and (said := getattr(params, spec.message_field, None)):
            self.store.append_message(pid, Message(phase=ph, role=Role.DEVELOPER, text=str(said), author=DEVELOPER))
        self._event(pid, "action.started", ph, f"{module.title}: {spec.label}", {"action": action})

        ctx = PhaseContext(
            project=project,
            phase=ph,
            store=self.store,
            llm=self.llm,
            renderer=self.renderer,
            log=lambda kind, summary, data: self._event(pid, kind, ph, summary, data),
        )
        try:
            outcome = module.run(action, params, ctx)
        except (LLMError, LLMOutputError) as err:
            self._event(pid, "phase.error", ph, str(err), {"action": action})
            raise ActionFailedError(str(err)) from err

        saved = [self._save(pid, a) for a in outcome.artifacts]
        stale = project.mark_changed(ph) if saved else []
        if outcome.status is not None:
            project.set_status(ph, outcome.status)
        self.store.save_project(project)
        self._log_stale(pid, ph, stale)
        if outcome.reply:
            self.store.append_message(pid, Message(phase=ph, role=Role.AGENT, text=outcome.reply, author=module.title, data=outcome.data))
        self._event(pid, "action.finished", ph, f"{module.title}: {spec.label} finished, phase is {project.status(ph).value}")
        return ActionResult(project=project, outcome=outcome.model_copy(update={"artifacts": saved}), stale=stale)

    def approve(self, project_id: str, phase: PhaseId | str) -> Project:
        project, ph = self.project(project_id), self.registry.get(phase).id
        project.approve(ph)
        self.store.save_project(project)
        self._event(project.id, "phase.approved", ph, f"Developer approved {ph.value}")
        return project

    def reopen(self, project_id: str, phase: PhaseId | str) -> Project:
        project, ph = self.project(project_id), self.registry.get(phase).id
        project.reopen(ph)
        self.store.save_project(project)
        self._event(project.id, "phase.reopened", ph, f"Developer reopened {ph.value}")
        return project

    # Developer edits

    def update_artifact(
        self, project_id: str, artifact_id: str, content: dict[str, Any] | None = None, text: str | None = None
    ) -> tuple[Artifact, list[PhaseId]]:
        project = self.project(project_id)
        current = self.store.get_artifact(project_id, artifact_id)
        module = self.registry.get(current.phase)
        edited = module.apply_developer_edit(current, content, text)
        saved = self._save(project_id, edited.model_copy(update={"author": DEVELOPER, "created_at": utcnow()}))
        stale = project.mark_changed(current.phase)
        self.store.save_project(project)
        self._log_stale(project_id, current.phase, stale)
        return saved, stale

    # Queries

    def trace(self, project_id: str) -> CoverageReport:
        self.project(project_id)
        return requirement_coverage(self.store.list_artifacts(project_id))

    # Internals

    def _save(self, project_id: str, artifact: Artifact) -> Artifact:
        saved = self.store.save_artifact(project_id, artifact)
        self._event(
            project_id,
            "artifact.saved",
            saved.phase,
            f"{saved.title} saved as revision {saved.revision} by {saved.author}",
            {"artifact": saved.id, "revision": saved.revision},
        )
        return saved

    def _log_stale(self, project_id: str, changed: PhaseId, stale: list[PhaseId]) -> None:
        for ph in stale:
            self._event(project_id, "phase.stale", ph, f"{ph.value} is stale because {changed.value} changed", {"cause": changed.value})

    def _event(self, project_id: str, kind: str, phase: PhaseId | None, summary: str, data: dict[str, Any] | None = None) -> Event:
        return self.store.append_event(project_id, Event(kind=kind, phase=phase, summary=summary, data=data or {}))
