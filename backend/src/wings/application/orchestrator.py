"""Orchestrator: the manager agent's deterministic half.

It owns the rules that must not depend on an LLM: which phase may run, what an
approval unlocks, what becomes stale after a change, and the activity log.
Phase modules do the work; the orchestrator calls them and records everything.

Consistency guarantees:
- One request per project at a time (a lock per project, held for the whole
  load, run, save sequence), so an edit made while an agent works is applied
  after it, never lost. Across processes the store's version check raises
  ConflictError instead of overwriting.
- All-or-nothing saves: every returned artifact is validated before the first
  one is written; a failure leaves no artifact, no developer message and an
  explanatory `phase.error` event.
- Wings see a copy of the project and a read-only store, and may only set the
  statuses in WING_STATUSES.
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from pydantic import BaseModel, Field

from wings.application.phase import ActionOutcome, PhaseContext
from wings.application.ports import ArtifactStore, DiagramRenderer, LLMClient, LLMError, ReadOnlyStore
from wings.application.registry import PhaseRegistry
from wings.application.structured import LLMOutputError
from wings.domain.activity import Event, Message, Role
from wings.domain.artifacts import DEVELOPER, Artifact
from wings.domain.errors import DomainError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.project import Project, slugify, utcnow
from wings.domain.trace import CoverageReport, requirement_coverage

# Statuses a wing may report. Approval is the developer's, staleness and locks are the orchestrator's.
WING_STATUSES = frozenset({PhaseStatus.NEEDS_INPUT, PhaseStatus.DRAFT})


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
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    @contextmanager
    def _exclusive(self, project_id: str) -> Iterator[None]:
        with self._locks_guard:
            lock = self._locks.setdefault(project_id, threading.RLock())
        with lock:
            yield

    # Projects

    def create_project(self, name: str) -> Project:
        base = slugify(name)
        with self._locks_guard:  # two creates with the same name must not pick the same id
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
        module = self.registry.get(phase)
        if not module.implemented:
            raise InvalidTransitionError(f"Phase '{module.id.value}' is planned but not implemented yet.")
        spec = module.action(action)
        if spec is None:
            raise NotFoundError(f"Phase '{module.id.value}' has no action '{action}'.")
        params = spec.input_model.model_validate(payload)  # pydantic.ValidationError -> HTTP 422

        with self._exclusive(project_id):
            project = self.project(project_id)
            project.ensure_can_run(module.id)
            pid, ph = project.id, module.id
            said = getattr(params, spec.message_field, None) if spec.message_field else None
            pending = [Message(phase=ph, role=Role.DEVELOPER, text=str(said), author=DEVELOPER)] if said else []
            self._event(pid, "action.started", ph, f"{module.title}: {spec.label}", {"action": action})

            ctx = PhaseContext(
                project=project.model_copy(deep=True),
                phase=ph,
                store=ReadOnlyStore(self.store),
                llm=self.llm,
                renderer=self.renderer,
                log=lambda kind, summary, data: self._event(pid, kind, ph, summary, data),
                pending=pending,
            )
            outcome = self._guarded(pid, ph, action, lambda: module.run(action, params, ctx))
            if outcome.status is not None and outcome.status not in WING_STATUSES:
                self._event(pid, "phase.error", ph, f"{module.title} tried to set status '{outcome.status.value}'", {"action": action})
                raise InvalidTransitionError(f"A wing may only report draft or needs_input, not {outcome.status.value}.")
            self._guarded(pid, ph, action, lambda: [self.store.check_artifact(pid, a) for a in outcome.artifacts])

            for message in pending:
                self.store.append_message(pid, message)
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
        ph = self.registry.get(phase).id
        with self._exclusive(project_id):
            project = self.project(project_id)
            project.approve(ph)
            self.store.save_project(project)
        self._event(project.id, "phase.approved", ph, f"Developer approved {ph.value}")
        return project

    def reopen(self, project_id: str, phase: PhaseId | str) -> Project:
        ph = self.registry.get(phase).id
        with self._exclusive(project_id):
            project = self.project(project_id)
            project.reopen(ph)
            self.store.save_project(project)
        self._event(project.id, "phase.reopened", ph, f"Developer reopened {ph.value}")
        return project

    # Developer edits

    def update_artifact(
        self, project_id: str, artifact_id: str, content: dict[str, Any] | None = None, text: str | None = None
    ) -> tuple[Artifact, list[PhaseId]]:
        with self._exclusive(project_id):
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

    def _guarded[T](self, project_id: str, phase: PhaseId, action: str, work: Callable[[], T]) -> T:
        """Run wing work; on any failure log a phase.error event so the activity log never ends at 'started'."""
        try:
            return work()
        except (LLMError, LLMOutputError) as err:
            self._event(project_id, "phase.error", phase, str(err), {"action": action})
            raise ActionFailedError(str(err)) from err
        except DomainError as err:
            self._event(project_id, "phase.error", phase, str(err), {"action": action})
            raise
        except Exception as err:
            self._event(project_id, "phase.error", phase, f"Internal error in {phase.value}: {err}", {"action": action})
            raise ActionFailedError(f"Internal error in {phase.value}: {err}") from err

    def _save(self, project_id: str, artifact: Artifact) -> Artifact:
        saved = self.store.save_artifact(project_id, artifact)
        self._event(
            project_id,
            "artifact.saved",
            saved.phase,
            f"{saved.title} {'retired' if saved.retired else 'saved'} as revision {saved.revision} by {saved.author}",
            {"artifact": saved.id, "revision": saved.revision},
        )
        return saved

    def _log_stale(self, project_id: str, changed: PhaseId, stale: list[PhaseId]) -> None:
        for ph in stale:
            self._event(project_id, "phase.stale", ph, f"{ph.value} is stale because {changed.value} changed", {"cause": changed.value})

    def _event(self, project_id: str, kind: str, phase: PhaseId | None, summary: str, data: dict[str, Any] | None = None) -> Event:
        return self.store.append_event(project_id, Event(kind=kind, phase=phase, summary=summary, data=data or {}))
