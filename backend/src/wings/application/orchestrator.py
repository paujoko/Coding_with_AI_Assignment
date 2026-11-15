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

from pydantic import BaseModel, Field

from wings.application.phase import ActionOutcome, PhaseContext
from wings.application.ports import ArtifactStore, DiagramRenderer, LLMClient, LLMError, ProjectFolder, ReadOnlyStore, Sandbox, TextExtractor
from wings.application.registry import PhaseRegistry
from wings.application.structured import LLMOutputError
from wings.domain.activity import Event, Message, Role
from wings.domain.artifacts import DEVELOPER, Artifact, ArtifactKind
from wings.domain.attachments import Attachment
from wings.domain.code import compare_design_and_code
from wings.domain.errors import ConflictError, DomainError, InvalidInputError, InvalidTransitionError, NotFoundError
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
        """`folder`: where the developer wants the files on their computer; checked before anything is created."""
        if folder and folder.strip():
            self._check_new_folder(folder.strip(), None)
        base = slugify(name)
        with self._locks_guard:  # two creates with the same name must not pick the same id
            pid, n = base, 1
            while self.store.project_exists(pid):
                n += 1
                pid = f"{base}-{n}"
            project = Project.new(name.strip() or pid, self.registry.dependencies(), project_id=pid)
            self.store.save_project(project)
        self._event(pid, "project.created", None, f"Project '{project.name}' created")
        if folder and folder.strip():
            self.set_folder(pid, folder)
            return self.project(pid)
        return project

    def project(self, project_id: str) -> Project:
        return self.store.load_project(project_id)

    def list_projects(self) -> list[Project]:
        return self.store.list_projects()

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
        self, project_id: str, phase: PhaseId | str, action: str, payload: dict[str, Any], attachments: list[str] | None = None
    ) -> ActionResult:
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
            said = getattr(params, spec.message_field, None) if spec.message_field else None
            if docs and not said:
                said = spec.label
            data = {"attachments": [d.ref for d in docs]} if docs else {}
            pending = [Message(phase=ph, role=Role.DEVELOPER, text=str(said), author=DEVELOPER, data=data)] if said else []
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
            stale = project.mark_changed(ph) if saved else []
            if outcome.status is not None:
                project.set_status(ph, outcome.status)
            if saved:
                self._sync(project)
            self.store.save_project(project)
            self._log_stale(pid, ph, stale)
            if outcome.reply:
                self.store.append_message(pid, Message(phase=ph, role=Role.AGENT, text=outcome.reply, author=module.title, data=outcome.data))
            self._event(pid, "action.finished", ph, f"{module.title}: {spec.label} finished, phase is {project.status(ph).value.replace('_', ' ')}")
            return ActionResult(project=project, outcome=outcome.model_copy(update={"artifacts": saved}), stale=stale)

    def approve(self, project_id: str, phase: PhaseId | str) -> Project:
        module = self.registry.get(phase)
        ph = module.id
        with self._exclusive(project_id):
            project = self.project(project_id)
            problem = module.approval_problem(self.store.list_artifacts(project_id))
            if problem:
                raise InvalidTransitionError(problem)
            project.approve(ph)
            self.store.save_project(project)
        self._event(project.id, "phase.approved", ph, f"{self.registry.get(ph).title} approved by the developer")
        return project

    def reopen(self, project_id: str, phase: PhaseId | str) -> Project:
        ph = self.registry.get(phase).id
        with self._exclusive(project_id):
            project = self.project(project_id)
            project.reopen(ph)
            self.store.save_project(project)
        self._event(project.id, "phase.reopened", ph, f"{self.registry.get(ph).title} reopened by the developer")
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
            self._sync(project)
            self.store.save_project(project)
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
            if project.folder is None or project.folder.path != path:
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
        report = compare_design_and_code(classes[0].text or "", code)
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
        same = project is not None and project.folder is not None and project.folder.path == path
        if not same and port.exists(path) and port.read_files(path):
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
        verbs = {"modified": "changed", "added": "new", "deleted": "deleted"}
        lines = ["Imported from your folder: " + ", ".join(f"{c.path} ({verbs[c.change]})" for c in imported) + "."]
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
