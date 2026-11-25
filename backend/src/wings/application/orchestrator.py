"""Orchestrator: the manager agent's deterministic half.

It owns the rules that must not depend on an LLM: which phase may run, what an
approval unlocks, what becomes stale after a change, and the activity log.
Phase modules do the work; the orchestrator calls them and records everything.

Consistency guarantees:
- One agent action per project at a time: a second one while an agent works is
  refused (ConflictError, HTTP 409) instead of queued; `running()` says what runs.
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

from pydantic import BaseModel, Field, ValidationError

from wings.application.phase import ActionOutcome, ActionSpec, PhaseContext, PhaseModule
from wings.application.ports import ArtifactStore, DiagramRenderer, LLMClient, LLMError, ProjectFolder, ReadOnlyStore, Sandbox, TextExtractor
from wings.application.registry import PhaseRegistry
from wings.application.structured import LLMOutputError
from wings.domain.activity import Event, Message, Role, decision, instruction
from wings.domain.artifacts import DEVELOPER, Artifact, ArtifactKind
from wings.domain.attachments import Attachment
from wings.domain.change import BaselineEntry, ChangeProgress, ChangeStep, ChangeView, OpenChange, PhaseReceipt, next_step, progress, receipt, receipt_markdown
from wings.domain.code import compare_design_and_code
from wings.domain.errors import ConflictError, DomainError, InvalidInputError, InvalidTransitionError, NotFoundError, PhaseLockedError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.folder import OutputFolder, SyncedFile
from wings.domain.project import Project, slugify, utcnow
from wings.domain.sync import FolderChange, FolderStatus, fingerprint, folder_changes, normalized, plan_export, program_path
from wings.domain.trace import CoverageReport, TraceView, current_design, requirement_coverage, trace_view

# Statuses a wing may report. Approval is the developer's, staleness and locks are the orchestrator's.
WING_STATUSES = frozenset({PhaseStatus.NEEDS_INPUT, PhaseStatus.DRAFT})

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024


class ActionFailedError(Exception):
    """The phase could not finish (LLM unreachable, unusable output). Nothing was saved."""


class ActionResult(BaseModel):
    project: Project
    outcome: ActionOutcome
    stale: list[PhaseId] = Field(default_factory=list)


class DesignCheck(BaseModel):
    """The current class diagram against the current code, computed by code (domain/code.py)."""

    diagram: str  # title of the class diagram compared with
    in_sync: bool
    lines: list[str] = Field(default_factory=list)


class FolderImport(BaseModel):
    project: Project
    imported: list[FolderChange] = Field(default_factory=list)
    skipped: list[FolderChange] = Field(default_factory=list)  # not importable, or not chosen
    stale: list[PhaseId] = Field(default_factory=list)
    drift: list[str] = Field(default_factory=list)  # design versus code after the import, computed by code
    reply: str = ""


class StepRun(BaseModel):
    """One action that `advance_change` ran."""

    phase: PhaseId
    action: str
    label: str
    status: PhaseStatus | None = None  # what the wing reported
    reply: str | None = None


class ChangeAdvance(BaseModel):
    """Result of carrying a change one phase further."""

    project: Project
    change: ChangeView
    ran: list[StepRun] = Field(default_factory=list)
    approved: PhaseId | None = None  # the phase approved on the developer's behalf in this call
    stopped_reason: str | None = None  # None: the next call can go on


class CatchUp(BaseModel):
    """Result of bringing one out-of-date phase up to date (`Orchestrator.catch_up`)."""

    project: Project
    ran: list[StepRun] = Field(default_factory=list)
    approved: PhaseId | None = None  # the phase approved on the developer's behalf in this call
    stopped_reason: str | None = None  # None: the next call can go on
    remaining: list[PhaseId] = Field(default_factory=list)  # phases still out of date, in pipeline order
    done: bool = False  # nothing is out of date any more


# Names the maintenance wing uses in a change's plan, where they differ from the phase ids.
PLAN_NAMES = {"code": PhaseId.CODEGEN, "tests": PhaseId.TESTING}

VERBS = {"modified": "changed", "added": "new", "deleted": "deleted"}  # a folder change in words


def _behalf(change: int | None, catch_up: bool) -> dict[str, Any] | None:
    """How a message records that Wings acted on the developer's behalf: carrying change `change`, catching up, or
    both (a catch-up step that is also the open change's next step). None: the developer acted themselves."""
    if catch_up:
        return {"catch_up": True} | ({"change": change} if change is not None else {})
    return {"change": change} if change is not None else None


class Orchestrator:
    def __init__(
        self,
        registry: PhaseRegistry,
        store: ArtifactStore,
        llm: LLMClient,
        renderer: DiagramRenderer,
        extractor: TextExtractor | None = None,
        sandbox: Sandbox | None = None,
        folder: ProjectFolder | None = None,
    ):
        self.registry = registry
        self.store = store
        self.llm = llm
        self.renderer = renderer
        self.extractor = extractor
        self.sandbox = sandbox
        self.folder = folder
        self._locks: dict[str, threading.RLock] = {}
        self._running: dict[str, dict[str, str]] = {}  # project id -> the agent action in progress
        self._locks_guard = threading.Lock()

    @contextmanager
    def _exclusive(self, project_id: str) -> Iterator[None]:
        with self._locks_guard:
            lock = self._locks.setdefault(project_id, threading.RLock())
        with lock:
            yield

    def running(self, project_id: str) -> dict[str, str] | None:
        """The agent action in progress for this project ({phase, action, label, started_at}), else None."""
        with self._locks_guard:
            found = self._running.get(project_id)
            return dict(found) if found else None

    @contextmanager
    def _claim(self, project_id: str, phase: PhaseId, action: str, label: str) -> Iterator[None]:
        """Mark the project busy for one agent action; a second action meanwhile is refused, not queued
        (real run s03: a second 'Write tests' waited six minutes and then ran again)."""
        with self._locks_guard:
            busy = self._running.get(project_id)
            if busy:
                raise ConflictError(
                    f"An agent is already working on this project ({busy['label']} in {busy['phase']}, since {busy['started_at'][11:19]} UTC). "
                    "Wait until it has finished."
                )
            self._running[project_id] = {"phase": phase.value, "action": action, "label": label, "started_at": utcnow().isoformat()}
        try:
            yield
        finally:
            with self._locks_guard:
                self._running.pop(project_id, None)

    # Projects

    def create_project(self, name: str, folder: str | None = None) -> Project:
        """`folder`: where the developer wants the files on their computer; checked before anything is created.
        Without one the project gets the default folder (`default_folder`), if this installation has one."""
        named = (folder or "").strip()
        if named:
            self._check_new_folder(named, None)
        base = slugify(name)
        chosen: str | None = None
        with self._locks_guard:  # two creates with the same name must not pick the same id
            pid, n = base, 1
            while self.store.project_exists(pid):
                n += 1
                pid = f"{base}-{n}"
            project = Project.new(name.strip() or pid, self.registry.dependencies(), project_id=pid)
            if not named:  # linked inside the lock, so a second create meanwhile cannot pick the same folder
                chosen = self.default_folder(name)
                if chosen is not None:
                    self._check_new_folder(chosen, None).prepare(chosen)
                    project.folder = OutputFolder(path=chosen)
            self.store.save_project(project)
        self._event(pid, "project.created", None, f"Project '{project.name}' created")
        if chosen is not None:
            self._event(pid, "folder.linked", None, f"Files of this project go to {chosen}")
        if named or chosen:
            self.set_folder(pid, named or chosen)
            return self.project(pid)
        return project

    def default_folder(self, name: str) -> str | None:
        """Where a project called `name` gets its files when the developer names no folder:
        `<projects dir>/<slug>`, or `<slug>-2`, `-3`, ... while that folder has something in it or belongs
        to another project. None when this installation has no projects dir. Creates nothing."""
        port = self.folder
        if port is None:
            return None
        base = slugify(name)
        taken = [p.folder.path for p in self.store.list_projects() if p.folder is not None]
        for n in range(1, 1000):
            candidate = port.default_path(base if n == 1 else f"{base}-{n}")
            if candidate is None:
                return None
            if port.is_empty(candidate) and not any(port.same(candidate, t) for t in taken):
                return candidate
        return None

    def project(self, project_id: str) -> Project:
        return self.store.load_project(project_id)

    def list_projects(self) -> list[Project]:
        return self.store.list_projects()

    def delete_project(self, project_id: str) -> None:
        """Forget a project: Wings' own record of it (artifacts, messages, documents, activity) is removed.
        The developer's folder is never touched; the files Wings wrote there stay. Refused while an agent
        works on the project, and no agent can start while the delete runs."""
        self.project(project_id)  # NotFoundError for an unknown id
        with self._locks_guard:
            busy = self._running.get(project_id)
            if busy:
                raise ConflictError(
                    f"An agent is working on this project ({busy['label']} in {busy['phase']}). "
                    "Wait until it has finished, then delete it."
                )
            self._running[project_id] = {"phase": "project", "action": "delete", "label": "Deleting the project", "started_at": utcnow().isoformat()}
        try:
            with self._exclusive(project_id):
                self.store.delete_project(project_id)
        finally:
            with self._locks_guard:
                self._running.pop(project_id, None)
                self._locks.pop(project_id, None)

    # Documents

    def add_attachment(self, project_id: str, name: str, media_type: str, data: bytes) -> Attachment:
        """Store an uploaded document with its text. Context only: no phase status changes."""
        self.project(project_id)
        name = name.replace("\\", "/").rsplit("/", 1)[-1].strip() or "document"
        if not data:
            raise InvalidInputError(f"'{name}' is empty.")
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise InvalidInputError(f"'{name}' is larger than {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.")
        if self.extractor is None:
            raise InvalidInputError("This installation cannot read documents (no text extractor configured).")
        text = self.extractor.extract(name, media_type, data)
        with self._exclusive(project_id):
            saved = self.store.save_attachment(project_id, Attachment(name=name, media_type=media_type, size=len(data), text=text), data)
        self._event(project_id, "attachment.added", None, f"{saved.name} added ({len(text):,} characters of text)", {"attachment": saved.id})
        return saved

    # Phase actions

    def run_action(
        self,
        project_id: str,
        phase: PhaseId | str,
        action: str,
        payload: dict[str, Any],
        attachments: list[str] | None = None,
        on_behalf: dict[str, Any] | None = None,
    ) -> ActionResult:
        """`on_behalf`: set when Wings runs the action itself while carrying a change or catching up
        ({"change": n} and/or {"catch_up": True}); what it says is then recorded as Wings', not the developer's."""
        module = self.registry.get(phase)
        if not module.implemented:
            raise InvalidTransitionError(f"Phase '{module.id.value}' is planned but not implemented yet.")
        spec = module.action(action)
        if spec is None:
            raise NotFoundError(f"Phase '{module.id.value}' has no action '{action}'.")
        params = spec.input_model.model_validate(payload)  # pydantic.ValidationError -> HTTP 422

        with self._claim(project_id, module.id, action, spec.label), self._exclusive(project_id):
            project = self.project(project_id)
            project.ensure_can_run(module.id)
            pid, ph = project.id, module.id
            docs = self._attachments(pid, attachments or [])
            pending = self._recorded(pid, ph, spec, params, docs, on_behalf)
            self._event(pid, "action.started", ph, f"{module.title}: {spec.label}", {"action": action})

            ctx = PhaseContext(
                project=project.model_copy(deep=True),
                phase=ph,
                store=ReadOnlyStore(self.store),
                llm=self.llm,
                renderer=self.renderer,
                log=lambda kind, summary, data: self._event(pid, kind, ph, summary, data),
                pending=pending,
                sandbox=self.sandbox,
            )
            outcome = self._guarded(pid, ph, action, lambda: module.run(action, params, ctx))
            if outcome.status is not None and outcome.status not in WING_STATUSES:
                self._event(pid, "phase.error", ph, f"{module.title} tried to set status '{outcome.status.value}'", {"action": action})
                raise InvalidTransitionError(f"A wing may only report draft or needs_input, not {outcome.status.value}.")
            self._guarded(pid, ph, action, lambda: [self.store.check_artifact(pid, a) for a in outcome.artifacts])

            for message in pending:
                self.store.append_message(pid, message)
            saved = [self._save(pid, a) for a in outcome.artifacts]
            stale = project.mark_changed(ph) if saved and outcome.changes_phase else []
            if outcome.status is not None and outcome.changes_phase:
                project.set_status(ph, outcome.status)
            if saved:
                self._sync(project)
            self.store.save_project(project)
            self._log_stale(pid, ph, stale)
            if outcome.reply:
                self.store.append_message(pid, Message(phase=ph, role=Role.AGENT, text=outcome.reply, author=module.title, data=outcome.data))
            self._event(pid, "action.finished", ph, f"{module.title}: {spec.label} finished, phase is {project.status(ph).value.replace('_', ' ')}")
            return ActionResult(project=project, outcome=outcome.model_copy(update={"artifacts": saved}), stale=stale)

    def _recorded(self, pid: str, ph: PhaseId, spec: ActionSpec, params: BaseModel, docs: list[Attachment], on_behalf: dict[str, Any] | None) -> list[Message]:
        """What this action puts in the step's conversation (ADR 0022), saved only if the action succeeds: the
        developer's choice as a decision line (the wing's `decision`, else the action's label when they typed
        nothing), then their words. On the developer's behalf: Wings' instruction, or its decision line, as Wings'."""
        raw = getattr(params, spec.message_field, None) if spec.message_field else None
        words = str(raw) if raw else ""
        if docs and not words:
            words = spec.label
        line = spec.decision(params, self.store.list_artifacts(pid)) if spec.decision else None
        details = params.model_dump(mode="json", exclude_unset=True, exclude={spec.message_field} if spec.message_field else None)
        if on_behalf:
            if words:
                return [instruction(ph, words, spec.name, spec.label, on_behalf)]
            return [decision(ph, line or spec.label, spec.name, details, on_behalf=on_behalf)]
        out = [decision(ph, line or spec.label, spec.name, details)] if line or not words else []
        if words:
            data = {"attachments": [d.ref for d in docs]} if docs else {}
            out.append(Message(phase=ph, role=Role.DEVELOPER, text=words, author=DEVELOPER, data=data))
        return out

    def approve(self, project_id: str, phase: PhaseId | str, change: int | None = None, catch_up: bool = False) -> Project:
        """`change`: set by `advance_change` when it approves on the developer's behalf; `catch_up`: set by
        `catch_up` for the same reason. The log says so either way."""
        module = self.registry.get(phase)
        ph = module.id
        with self._exclusive(project_id):
            project = self.project(project_id)
            artifacts = self.store.list_artifacts(project_id)
            problem = module.approval_problem(artifacts)
            if problem:
                raise InvalidTransitionError(problem)
            note = module.approval_note(artifacts)  # never blocks; said with the approval (ADR 0020)
            was, cause = project.status(ph), project.phases[ph].stale_cause
            project.approve(ph)
            self._close_change(project)
            self.store.save_project(project)
            # The line in the step's conversation (ADR 0022); the note is Wings', kept apart from the decision.
            behalf = _behalf(change, catch_up)
            kept = was is PhaseStatus.STALE and behalf is None
            if behalf:
                text = "Accepted on your behalf: its checks pass"
            elif kept:
                text = f"Kept unchanged, although {self.registry.get(cause).title} changed" if cause else "Kept unchanged"
            else:
                text = module.acceptance(artifacts)
            line = decision(ph, text, "approve", {"kept": True} if kept else None, on_behalf=behalf)
            self.store.append_message(project_id, line.model_copy(update={"data": line.data | ({"note": note} if note else {})}))
        said = f". {note}" if note else ""
        extra: dict[str, Any] = {"note": note} if note else {}
        if catch_up:
            data: dict[str, Any] = {"catch_up": True, "on_behalf": True} | ({"change": change} if change is not None else {}) | extra
            self._event(project.id, "phase.approved", ph, f"{module.title} approved as part of bringing the project up to date, at the developer's request{said}", data)
        elif change is None:
            self._event(project.id, "phase.approved", ph, f"{module.title} approved by the developer{said}", extra or None)
        else:
            summary = f"{module.title} approved as part of carrying change #{change} through, at the developer's request{said}"
            self._event(project.id, "phase.approved", ph, summary, {"change": change, "on_behalf": True} | extra)
        return project

    def approval_note(self, project_id: str, phase: PhaseId | str) -> str | None:
        """What the phase says when it is approved (never blocks), e.g. Tests: how many requirements a
        passing test verifies (ADR 0020). For the CLI and MCP; the event of `approve` carries it too."""
        self.project(project_id)
        return self.registry.get(phase).approval_note(self.store.list_artifacts(project_id))

    def reopen(self, project_id: str, phase: PhaseId | str) -> Project:
        ph = self.registry.get(phase).id
        with self._exclusive(project_id):
            project = self.project(project_id)
            project.reopen(ph)
            self.store.save_project(project)
            self.store.append_message(project_id, decision(ph, "Reopened", "reopen"))
        self._event(project.id, "phase.reopened", ph, f"{self.registry.get(ph).title} reopened by the developer")
        return project

    # Changes carried through the phases (rules in domain/change.py)

    def changes(self, project_id: str) -> list[ChangeView]:
        """Every tracked change request, newest first, with progress, next step and receipt."""
        project = self.project(project_id)
        return self._changes(project, self.store.list_artifacts(project_id))

    def open_change(self, project_id: str) -> OpenChange | None:
        """The change in progress (the newest one, while it is open), for the project view."""
        found = self.changes(project_id)
        if not found or found[0].state != "open":
            return None
        return OpenChange(number=found[0].number, done=found[0].progress.done, total=found[0].progress.total, next_phase=found[0].progress.current)

    def advance_change(self, project_id: str, number: int, approve: bool = True) -> ChangeAdvance:
        """Carry change `number` one phase further: run the next step of its current phase through
        `run_action` (every gate applies) and, if `approve` is set, the wing reported a draft and the
        phase's own gate is open, approve the phase on the developer's behalf. One phase per call, never a
        loop: the caller decides whether to go on. `stopped_reason` says why it cannot (open questions,
        a failed check, a failed action, approval left to the developer)."""
        view = self._change(project_id, number)
        step = view.next
        ran: list[StepRun] = []
        approved: PhaseId | None = None
        reason: str | None = None
        if view.state != "open" or step is None:
            reason = f"Change {number} is {'complete' if view.state == 'complete' else 'closed'}; there is nothing left to carry through."
        elif step.kind in ("input", "blocked"):
            reason = step.reason
        else:
            module = self.registry.get(step.phase)
            if step.kind == "run":
                labels = ", then ".join(s.label or s.action for s in step.steps)
                self._event(project_id, "change.advance", step.phase, f"Change #{number}: updating {module.title} ({labels})", {"change": number})
            ran, approved, reason = self._update_phase(project_id, module, step.steps if step.kind == "run" else [], approve, change=number)
            if approved is not None and self._change(project_id, number).state == "complete":
                self._check_after_change(project_id, {"change": number})
        if reason is not None:
            self._event(project_id, "change.stopped", step.phase if step else None, f"Change #{number} waits: {reason}", {"change": number})
        return ChangeAdvance(project=self.project(project_id), change=self._change(project_id, number), ran=ran, approved=approved, stopped_reason=reason)

    def _update_phase(
        self, project_id: str, module: PhaseModule, steps: list[ChangeStep], approve: bool, change: int | None = None, catch_up: bool = False
    ) -> tuple[list[StepRun], PhaseId | None, str | None]:
        """The part `advance_change` and `catch_up` share: run `steps` of one phase through `run_action` (every
        gate applies) and, with `approve`, approve the phase on the developer's behalf if the wing reported a
        draft and its own gate is open. Returns what ran, the phase approved, and why it stopped (None: it can
        go on). With no steps the phase is only approved (it already has a draft)."""
        ran: list[StepRun] = []
        for s in steps:
            try:
                result = self.run_action(project_id, s.phase, s.action, s.input, on_behalf=_behalf(change, catch_up))
            except (ActionFailedError, InvalidTransitionError, PhaseLockedError, InvalidInputError, ValidationError) as err:
                return ran, None, f"{module.title}: '{s.label or s.action}' did not finish. {err}"
            ran.append(StepRun(phase=s.phase, action=s.action, label=s.label, status=result.outcome.status, reply=result.outcome.reply))
            if result.outcome.status is PhaseStatus.NEEDS_INPUT:
                return ran, None, f"{module.title} has open questions. Answer them in the phase, then continue."
            if result.outcome.status is not PhaseStatus.DRAFT:
                return ran, None, f"{module.title} produced no new result: {result.outcome.reply or 'no reply'}"
        if not approve:
            return ran, None, f"{module.title} is ready for review. Accept it to continue."
        problem = module.approval_problem(self.store.list_artifacts(project_id))
        if problem is not None:
            return ran, None, problem
        try:
            self.approve(project_id, module.id, change=change, catch_up=catch_up)
        except (InvalidTransitionError, PhaseLockedError) as err:
            return ran, None, str(err)
        return ran, module.id, None

    # Bringing a stale project up to date (no tracked change needed)

    def stale_phases(self, project: Project) -> list[PhaseId]:
        """Phases whose output is out of date, in pipeline order. Maintenance is never part of it."""
        return [m.id for m in self.registry.ordered() if m.id is not PhaseId.MAINTENANCE and project.status(m.id) is PhaseStatus.STALE]

    def catch_up(self, project_id: str, approve: bool = True) -> CatchUp:
        """Bring the first out-of-date phase up to date: its wing's own refresh step runs through `run_action`
        (every gate applies) and, with `approve`, the phase is approved on the developer's behalf when the wing
        reported a draft and its gate is open. One phase per call, never a loop. If a tracked change is open and
        plans that phase, this does exactly what `advance_change` would. `stopped_reason` says why it cannot go
        on (open questions, a failed check or action, a phase to update by hand, approval left to the developer)."""
        project = self.project(project_id)
        stale = self.stale_phases(project)
        if not stale:
            return CatchUp(project=project, stopped_reason="Everything is up to date.", done=True)
        target = stale[0]
        module = self.registry.get(target)
        artifacts = self.store.list_artifacts(project_id)
        views = self._changes(project, artifacts)
        open_view = views[0] if views and views[0].state == "open" else None
        planned_next = open_view is not None and open_view.next is not None and open_view.next.phase is target and open_view.next.kind == "run"
        waiting = [self.registry.get(d).title for d in project.upstream(target) if project.status(d) is not PhaseStatus.APPROVED]
        ran: list[StepRun] = []
        approved: PhaseId | None = None
        reason: str | None = None
        steps: list[ChangeStep] = []
        if waiting:
            reason = f"{', '.join(waiting)} must be accepted before {module.title} can be redone. Check it and accept it first."
        elif open_view is not None and open_view.next is not None and planned_next:
            steps = open_view.next.steps  # the very steps advance_change would run
        else:
            steps = self._refresh_steps(module, self._stale_reason(project, target, artifacts, open_view), artifacts)
            if not steps:
                reason = f"{module.title} cannot be redone by itself. Change it in its step, then accept it."
        if reason is None:
            labels = ", then ".join(s.label or s.action for s in steps)
            self._event(project_id, "catchup.advance", target, f"Catching up: updating {module.title} ({labels})", {"catch_up": True})
            number = open_view.number if open_view is not None and planned_next else None
            ran, approved, reason = self._update_phase(project_id, module, steps, approve, change=number, catch_up=True)
            if approved is not None and open_view is not None and self._change(project_id, open_view.number).state == "complete":
                self._check_after_change(project_id, {"catch_up": True, "change": open_view.number})
        if reason is not None:
            self._event(project_id, "catchup.stopped", target, f"Catching up waits: {reason}", {"catch_up": True})
        after = self.project(project_id)
        remaining = self.stale_phases(after)
        return CatchUp(project=after, ran=ran, approved=approved, stopped_reason=reason, remaining=remaining, done=not remaining and reason is None)

    def _refresh_steps(self, module: PhaseModule, reason: str, artifacts: list[Artifact]) -> list[ChangeStep]:
        steps = []
        for name, payload in module.refresh_step(reason, artifacts):
            spec = module.action(name)
            steps.append(ChangeStep(phase=module.id, action=name, input=payload, label=spec.label if spec else name))
        return steps

    def _stale_reason(self, project: Project, phase: PhaseId, artifacts: list[Artifact], open_view: ChangeView | None) -> str:
        """What changed upstream, in words, for a wing's refresh step."""
        cause = project.phases[phase].stale_cause
        title = self.registry.get(phase).title
        lines = [f"{self.registry.get(cause).title} changed, so {title} is out of date." if cause else f"{title} is out of date."]
        if cause is not None:
            mine = [a for a in artifacts if a.phase is cause and not a.retired]
            made = [a.created_at for a in mine if a.author != DEVELOPER]
            by_hand = sorted(a.path or a.title for a in mine if a.author == DEVELOPER and (not made or a.created_at > max(made)))
            if by_hand:
                lines.append(f"The developer edited by hand: {', '.join(by_hand)}.")
        if open_view is not None:
            lines += [f"Change {open_view.number}: {open_view.summary}", f"The developer asked: {open_view.request}"]
        return "\n".join(lines)

    def _check_after_change(self, project_id: str, on_behalf: dict[str, Any]) -> None:
        """When a change is carried through, run Maintenance's own re-check step (computed by code), so the
        developer sees at once whether design, code and tests agree, instead of an out-of-date step."""
        module = self.registry.get(PhaseId.MAINTENANCE)
        for action, payload in module.refresh_step("A change was carried through.", self.store.list_artifacts(project_id)):
            try:
                self.run_action(project_id, PhaseId.MAINTENANCE, action, payload, on_behalf=on_behalf)
            except (ActionFailedError, InvalidTransitionError, PhaseLockedError, InvalidInputError) as err:
                self._event(project_id, "phase.error", PhaseId.MAINTENANCE, f"Check after the change failed: {err}", {})
                return

    def _change(self, project_id: str, number: int) -> ChangeView:
        found = next((c for c in self.changes(project_id) if c.number == number), None)
        if found is None:
            raise NotFoundError(f"Project '{project_id}' has no tracked change {number}.")
        return found

    def _changes(self, project: Project, artifacts: list[Artifact]) -> list[ChangeView]:
        """Change requests without a baseline (made before change tracking existed) are left out."""
        records = [a for a in artifacts if a.kind is ArtifactKind.CHANGE_REQUEST and not a.retired and isinstance(a.content.get("baseline"), dict)]
        records.sort(key=lambda a: int(a.content.get("number", 0)), reverse=True)
        return [self._change_view(project, artifacts, a, newest=i == 0) for i, a in enumerate(records)]

    def _change_view(self, project: Project, artifacts: list[Artifact], record: Artifact, newest: bool) -> ChangeView:
        c = record.content
        titles = {m.id: m.title for m in self.registry.ordered()}
        closed = c.get("closed")
        # A change closed before progress required every planned phase to be updated (no `planned` in its frozen
        # progress) is not trusted: it is shown live, and closed again with a fresh receipt once it is complete.
        if closed and newest and "planned" not in closed.get("progress", {}):
            closed = None
        step: Any = None
        completed_at = None
        if closed:
            state = ChangeProgress.model_validate(closed["progress"])
            found = [PhaseReceipt.model_validate(r) for r in closed["receipt"]]
            completed_at = closed.get("completed_at")
        else:
            tracked = [m.id for m in self.registry.ordered() if m.implemented and m.id is not record.phase]
            baseline = {aid: BaselineEntry.model_validate(entry) for aid, entry in c["baseline"].items()}
            first = ChangeStep.model_validate(c["first_step"]) if c.get("first_step") else None
            planned = [PLAN_NAMES.get(n) or PhaseId(n) for n in c["phases"] if n in PLAN_NAMES or n in PhaseId._value2member_map_] if c.get("phases") else None
            state = progress(project, tracked, baseline, artifacts, first, planned)
            found = receipt(baseline, artifacts, tracked)
            if newest and state.current is not None:
                module = self.registry.get(state.current)
                refresh = self._refresh_steps(module, self._change_reason(c), artifacts)
                problem = module.approval_problem(artifacts) if project.status(module.id) is PhaseStatus.DRAFT else None
                step = next_step(state, project, first, refresh, problem, title=module.title)
        for entry in [*state.phases, *found]:
            entry.title = titles.get(entry.phase, entry.phase.value)
        # An open change that is not the newest was never started: a new one can only be requested when
        # every phase is approved, and a started change is closed at that moment.
        status = "complete" if state.complete else "open" if newest else "dropped"
        return ChangeView(
            number=int(c.get("number", 0)),
            artifact_id=record.id,
            kind=str(c.get("kind", "change")),
            request=str(c.get("request", "")),
            summary=str(c.get("summary", "")),
            affected=list(c.get("affected", [])),
            state=status,
            started_at=c.get("started_at") or record.created_at,
            completed_at=completed_at,
            progress=state,
            next=step,
            receipt=found,
        )

    @staticmethod
    def _change_reason(content: dict[str, Any]) -> str:
        """The change in words, handed to each wing's refresh step."""
        lines = [f"Change {content.get('number')}: {content.get('summary', '')}", f"The developer asked: {content.get('request', '')}"]
        detail = content.get("requirements_update") or content.get("fix")
        if detail:
            lines.append(str(detail))
        return "\n".join(lines)

    def _close_change(self, project: Project) -> None:
        """Called when a phase was approved: if that completed the newest change, freeze its progress and
        receipt in the change artifact, so later changes do not rewrite what this one did."""
        artifacts = self.store.list_artifacts(project.id)
        views = self._changes(project, artifacts)
        if not views or not views[0].progress.complete:
            return
        view = views[0]
        record = next(a for a in artifacts if a.id == view.artifact_id)
        frozen = record.content.get("closed")
        if frozen and "planned" in frozen.get("progress", {}):
            return
        now = utcnow()
        closed = {
            "completed_at": now.isoformat(),
            "progress": view.progress.model_dump(mode="json"),
            "receipt": [r.model_dump(mode="json") for r in view.receipt],
        }
        count = sum(r.count for r in view.receipt)
        text = (
            (record.text or "").split("\n\n## Carried through")[0]
            + f"\n\n## Carried through\n\nComplete since {now.strftime('%Y-%m-%d %H:%M')} UTC. "
            + f"{count} artifact(s) updated, added or removed (computed by code):\n\n"
            + receipt_markdown(view.receipt)
        )
        content = record.content | {"closed": closed, "started_at": record.created_at.isoformat()}
        self._save(project.id, record.model_copy(update={"content": content, "text": text, "author": "system:change-tracking", "created_at": now}))
        self._sync(project)
        phases = ", ".join(r.title for r in view.receipt if r.count)
        self._event(project.id, "change.completed", record.phase, f"Change #{view.number} is carried through: {count} artifact(s) changed in {phases}", {"change": view.number})

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
            self._sync(project)
            self.store.save_project(project)
            line = f"Edited {saved.path or saved.title} (revision {saved.revision})"
            self.store.append_message(project_id, decision(current.phase, line, "edit", {"artifact": saved.id, "revision": saved.revision}))
            self._log_stale(project_id, current.phase, stale)
            return saved, stale

    # Output folder (ADR 0015): Wings -> folder after every change, folder -> Wings when the developer imports

    def set_folder(self, project_id: str, path: str | None) -> FolderStatus:
        """Link the project to a folder on the developer's computer (and write every file there), or unlink it
        (None). A new folder must be empty or missing, so Wings never mixes its files with someone else's."""
        with self._exclusive(project_id):
            project = self.project(project_id)
            if path is None or not path.strip():
                if project.folder is not None:
                    old = project.folder.path
                    project.folder = None
                    self.store.save_project(project)
                    self._event(project_id, "folder.unlinked", None, f"Folder {old} unlinked; its files stay where they are")
                return FolderStatus(path=None)
            path = path.strip()
            port = self._check_new_folder(path, project)
            port.prepare(path)
            if project.folder is None or not port.same(project.folder.path, path):  # another spelling of the same folder keeps its manifest
                project.folder = OutputFolder(path=path)
                self._event(project_id, "folder.linked", None, f"Files of this project go to {path}")
            self._sync(project)
            self.store.save_project(project)
        return self.folder_status(project_id)

    def folder_status(self, project_id: str) -> FolderStatus:
        """What changed in the folder since Wings last wrote it: hand edits, deletions, new code files.
        Each change says whether it can be imported, after the owning wing has looked at the content."""
        project = self.project(project_id)
        if project.folder is None:
            return FolderStatus(path=None)
        path = project.folder.path
        if self.folder is None:
            return FolderStatus(path=path, problem="This installation has no folder support.")
        if not self.folder.exists(path):
            return FolderStatus(path=path, exists=False, problem=f"The folder {path} is not there (moved, deleted, or on a drive that is not connected).")
        artifacts = self.store.list_artifacts(project_id)
        disk = self.folder.read_files(path)
        by_id = {a.id: a for a in artifacts}
        checked = [self._vet(c, by_id, disk) for c in folder_changes(artifacts, project.folder.files, disk)]
        return FolderStatus(path=path, changes=[c for c in checked if c is not None])

    def import_folder_changes(self, project_id: str, paths: list[str] | None = None) -> FolderImport:
        """Folder -> Wings: the chosen hand edits become new revisions by the developer (all importable
        changes when `paths` is None). The changed phases go back to draft, their dependants become stale,
        and design versus code is checked again by code."""
        port = self._folder_port()
        with self._exclusive(project_id):
            status = self.folder_status(project_id)
            if status.path is None or status.problem:
                raise InvalidInputError(status.problem or "This project has no folder on your computer yet; set one first.")
            project = self.project(project_id)
            assert project.folder is not None  # checked above, inside the same lock
            wanted = set(paths) if paths is not None else None
            chosen = [c for c in status.changes if c.importable and (wanted is None or c.path in wanted)]
            skipped = [c for c in status.changes if c not in chosen]
            if not chosen:
                raise InvalidInputError("Nothing to import: no importable change in the folder" + (" among the files you chose." if wanted else "."))
            disk = port.read_files(project.folder.path)
            by_id = {a.id: a for a in self.store.list_artifacts(project_id)}
            order = {m.id: i for i, m in enumerate(self.registry.ordered())}
            chosen.sort(key=lambda c: (order.get(c.phase, 99) if c.phase else 99, c.path))
            # All or nothing: every new revision is built and checked before the first is saved.
            revisions = [self._take_over(c, by_id, disk) for c in chosen]
            for artifact in revisions:
                self.store.check_artifact(project_id, artifact)
            changed: set[PhaseId] = set()
            imported: list[FolderChange] = []
            for change, artifact in zip(chosen, revisions):
                saved = self._save(project_id, artifact)
                if change.change == "deleted":
                    project.folder.files.pop(change.path, None)
                else:
                    project.folder.files[change.path] = SyncedFile(artifact_id=saved.id, revision=saved.revision, sha256=fingerprint(disk[change.path]))
                changed.add(saved.phase)
                imported.append(change.model_copy(update={"artifact_id": saved.id, "phase": saved.phase}))
            stale: list[PhaseId] = []
            for ph in sorted(changed, key=lambda p: order[p]):
                stale += [s for s in project.mark_changed(ph) if s not in stale]
            stale = [s for s in stale if s not in changed]  # a phase the developer edited is draft, not stale
            self._sync(project)
            self.store.save_project(project)
            first = min(changed, key=lambda p: order[p])
            self._log_stale(project_id, first, stale)
            self._event(project_id, "folder.imported", first, f"{len(imported)} change(s) imported from the folder: {', '.join(c.path for c in imported)}", {"paths": [c.path for c in imported]})
            drift, diagram = self._drift_after_import(project_id, changed)
            reply, actions = self._import_reply(imported, stale, drift, diagram)
            for ph in sorted(changed, key=lambda p: order[p]):
                # The developer's decision first (ADR 0022), then what code found.
                mine = [c for c in imported if c.phase == ph]
                listing = ", ".join(f"{c.path} ({VERBS[c.change]})" for c in mine)
                self.store.append_message(project_id, decision(ph, f"Imported from your folder: {listing}", "import", {"paths": [c.path for c in mine]}))
                # No model wrote this: `speaker` lets the conversation say so instead of naming the phase's agent.
                # `drift` lets the UI show the message as resolved once design and code agree again.
                data: dict[str, Any] = {"speaker": "Folder sync, checked by code", "drift": drift} | ({"next_actions": actions} if actions else {})
                self.store.append_message(project_id, Message(phase=ph, role=Role.AGENT, text=reply, author="Folder sync (code)", data=data))
            return FolderImport(project=project, imported=imported, skipped=skipped, stale=stale, drift=drift, reply=reply)

    def restore_folder_files(self, project_id: str, paths: list[str]) -> FolderStatus:
        """Wings -> folder for files the developer changed or deleted by hand: put Wings' version back.
        Only what the developer names is touched; new files they created are never removed."""
        port = self._folder_port()
        with self._exclusive(project_id):
            status = self.folder_status(project_id)
            if status.path is None or status.problem:
                raise InvalidInputError(status.problem or "This project has no folder on your computer yet; set one first.")
            project = self.project(project_id)
            assert project.folder is not None  # checked above, inside the same lock
            by_path = {c.path: c for c in status.changes if c.change in ("modified", "deleted")}
            unknown = [p for p in paths if p not in by_path]
            if unknown:
                raise InvalidInputError(f"Not a changed or deleted file of this project: {', '.join(unknown)}.")
            by_id = {a.id: a for a in self.store.list_artifacts(project_id)}
            for p in paths:
                artifact = by_id[by_path[p].artifact_id or ""]
                port.write_file(project.folder.path, p, artifact.text or "")
                project.folder.files[p] = SyncedFile(artifact_id=artifact.id, revision=artifact.revision, sha256=fingerprint(artifact.text or ""))
            self.store.save_project(project)
            by_phase: dict[PhaseId, list[str]] = {}
            for p in paths:
                by_phase.setdefault(by_id[by_path[p].artifact_id or ""].phase, []).append(p)
            for ph, mine in by_phase.items():
                self.store.append_message(project_id, decision(ph, f"Put Wings' version back in your folder: {', '.join(mine)}", "restore", {"paths": mine}))
            self._event(project_id, "folder.restored", None, f"Wings' version written back to the folder: {', '.join(paths)}", {"paths": paths})
        return self.folder_status(project_id)

    # Queries

    def design_check(self, project_id: str) -> DesignCheck | None:
        """Does the code still match the class diagram of the current design? None when there is no
        class diagram or no code yet. Used after an import and to say whether out-of-date code still fits."""
        self.project(project_id)
        artifacts = self.store.list_artifacts(project_id)
        classes = [d for d in current_design(artifacts) if d.content.get("kind") == "class"]
        code = {a.content.get("path", a.title): a.text or "" for a in artifacts if a.kind is ArtifactKind.SOURCE_FILE and not a.retired}
        if not classes or not code:
            return None
        report = compare_design_and_code([d.text or "" for d in classes], code)  # all class diagrams together
        return DesignCheck(diagram=classes[0].title, in_sync=report.in_sync, lines=report.lines())

    def trace(self, project_id: str) -> CoverageReport:
        self.project(project_id)
        return requirement_coverage(self.store.list_artifacts(project_id))

    def trace_view(self, project_id: str) -> TraceView:
        self.project(project_id)
        return trace_view(self.store.list_artifacts(project_id))

    # Internals

    def _folder_port(self) -> ProjectFolder:
        if self.folder is None:
            raise InvalidInputError("This installation has no folder support.")
        return self.folder

    def _check_new_folder(self, path: str, project: Project | None) -> ProjectFolder:
        port = self._folder_port()
        problem = port.problem(path)
        if problem:
            raise InvalidInputError(problem)
        same = project is not None and project.folder is not None and port.same(project.folder.path, path)
        if not same and not port.is_empty(path):
            raise InvalidInputError(f"{path} already has files in it. Choose an empty or a new folder, so Wings never mixes its files with others.")
        return port

    def _sync(self, project: Project) -> None:
        """Wings -> folder after a change: write the current files, never over a hand edit (domain/sync.py).
        A folder problem is logged and never fails the change itself; the caller saves the project."""
        if project.folder is None or self.folder is None:
            return
        path = project.folder.path
        try:
            if not self.folder.exists(path):
                self._event(project.id, "folder.error", None, f"The folder {path} is not there; files were not written")
                return
            plan = plan_export(self.store.list_artifacts(project.id), project.folder.files, self.folder.read_files(path))
            for rel, text in plan.writes.items():
                self.folder.write_file(path, rel, text)
            for rel in plan.deletes:
                self.folder.delete_file(path, rel)
        except (OSError, ValueError) as err:
            self._event(project.id, "folder.error", None, f"Writing to {path} failed: {err}")
            return
        project.folder.files = plan.files
        project.folder.synced_at = utcnow()
        if plan.writes or plan.deletes or plan.kept:
            summary = f"{len(plan.writes)} file(s) written to the folder, {len(plan.deletes)} removed"
            if plan.kept:
                summary += f"; left alone because changed by hand: {', '.join(plan.kept)}"
            self._event(project.id, "folder.synced", None, summary, {"written": sorted(plan.writes), "deleted": plan.deletes, "kept": plan.kept})

    def _vet(self, change: FolderChange, by_id: dict[str, Artifact], disk: dict[str, str]) -> FolderChange | None:
        """Ask the owning wing whether the content is acceptable. New files nobody owns are dropped."""
        if change.change == "deleted" or not change.importable and change.change == "modified":
            return change
        text = normalized(disk[change.path])
        try:
            if change.change == "modified":
                current = by_id[change.artifact_id or ""]
                self.registry.get(current.phase).apply_developer_edit(current, None, text)
                return change
            adopted = self._adopt(program_path(change.path) or change.path, text)
            if adopted is None:
                return None
            clash = by_id.get(adopted.id)
            if clash is not None and not clash.retired:
                return change.model_copy(update={"artifact_id": adopted.id, "phase": adopted.phase, "importable": False, "note": f"Would be stored as the same file as {clash.title}; rename it."})
            return change.model_copy(update={"artifact_id": adopted.id, "phase": adopted.phase, "importable": True})
        except (InvalidInputError, ValueError) as err:
            return change.model_copy(update={"importable": False, "note": f"Cannot be imported: {err}"})

    def _adopt(self, path: str, text: str) -> Artifact | None:
        for module in self.registry.ordered():
            adopted = module.adopt_developer_file(path, text)
            if adopted is not None:
                return adopted
        return None

    def _take_over(self, change: FolderChange, by_id: dict[str, Artifact], disk: dict[str, str]) -> Artifact:
        """The new revision (not saved yet) that one imported change becomes; the developer is its author."""
        now = {"author": DEVELOPER, "created_at": utcnow()}
        if change.change == "deleted":
            return by_id[change.artifact_id or ""].model_copy(update={"retired": True, **now})
        text = normalized(disk[change.path])
        if change.change == "modified":
            current = by_id[change.artifact_id or ""]
            return self.registry.get(current.phase).apply_developer_edit(current, None, text).model_copy(update=now)
        adopted = self._adopt(program_path(change.path) or change.path, text)
        if adopted is None:
            raise InvalidInputError(f"{change.path} is not a file Wings can keep.")
        return adopted.model_copy(update=now)

    def _drift_after_import(self, project_id: str, changed: set[PhaseId]) -> tuple[list[str], str]:
        """Design versus code after an import that touched either of them: (lines, class diagram title)."""
        if not changed & {PhaseId.CODEGEN, PhaseId.DESIGN, PhaseId.REFINEMENT}:
            return [], ""
        check = self.design_check(project_id)
        return (check.lines, check.diagram) if check else ([], "")

    def _import_reply(self, imported: list[FolderChange], stale: list[PhaseId], drift: list[str], diagram: str) -> tuple[str, list[dict[str, Any]]]:
        lines = ["Imported from your folder: " + ", ".join(f"{c.path} ({VERBS[c.change]})" for c in imported) + "."]
        if stale:
            lines.append("Out of date now: " + ", ".join(self.registry.get(s).title for s in stale) + ".")
        actions: list[dict[str, Any]] = []
        if drift:
            listing = "; ".join(drift)
            lines.append("Design and code disagree (checked by code):\n- " + "\n- ".join(drift))
            lines.append("Pick a direction: update the design to match your code, or the code to match the design.")
            actions = [
                {"label": "Update the design from the code", "phase": PhaseId.REFINEMENT.value, "action": "comment", "input": {"diagram": diagram, "comment": f"Update the diagrams to match the code: {listing}"}},
                {"label": "Update the code from the design", "phase": PhaseId.CODEGEN.value, "action": "revise", "input": {"feedback": f"Make the code match the class diagram: {listing}"}},
            ]
        elif diagram:
            lines.append("Checked by code: design and code still agree.")
        return "\n".join(lines), actions

    def _attachments(self, project_id: str, ids: list[str]) -> list[Attachment]:
        found = []
        for aid in dict.fromkeys(ids):
            try:
                found.append(self.store.get_attachment(project_id, aid))
            except NotFoundError as err:
                raise InvalidInputError(f"There is no attached document '{aid}' in this project.") from err
        return found

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
            f"{saved.title}: revision {saved.revision} {'retired' if saved.retired else 'saved'} by {saved.author.removeprefix('agent:')}",
            {"artifact": saved.id, "revision": saved.revision},
        )
        return saved

    def _log_stale(self, project_id: str, changed: PhaseId, stale: list[PhaseId]) -> None:
        for ph in stale:
            title, cause = self.registry.get(ph).title, self.registry.get(changed).title
            self._event(project_id, "phase.stale", ph, f"{title} is out of date because {cause} changed", {"cause": changed.value})

    def _event(self, project_id: str, kind: str, phase: PhaseId | None, summary: str, data: dict[str, Any] | None = None) -> Event:
        return self.store.append_event(project_id, Event(kind=kind, phase=phase, summary=summary, data=data or {}))
