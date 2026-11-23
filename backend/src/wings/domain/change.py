"""Change tracking: how far a change request got through the phases, computed by code.

When a change is requested, the maintenance wing records a baseline: every artifact id with the
revision it had at that moment. Everything else follows from comparing that baseline with the
artifacts and phase statuses of now:

- `progress`: per phase one of `done` (changed since the baseline and approved), `current` (the
  one to act on), `waiting` (behind the current one) or `untouched` (approved and not changed).
- `next_step`: what to do in the current phase (run actions, approve, answer questions, or blocked).
- `receipt`: per phase the artifacts this change updated, added or removed. This is the evidence
  of which artefacts a change reached.

Pure functions, no I/O. The orchestrator runs them and closes a change (freezes progress and
receipt) once every phase is approved again.
"""

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from wings.domain.artifacts import Artifact
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.project import Project

PhaseChangeState = Literal["done", "current", "waiting", "untouched"]
ChangeState = Literal["open", "complete", "dropped"]
NextKind = Literal["run", "approve", "input", "blocked"]


class BaselineEntry(BaseModel):
    revision: int
    retired: bool = False
    digest: str = ""  # fingerprint of text and content, to tell a real change from an identical new revision


class ChangeStep(BaseModel):
    """One action of one phase, with the input to run it with."""

    phase: PhaseId
    action: str
    input: dict[str, Any] = Field(default_factory=dict)
    label: str = ""


class ArtifactChange(BaseModel):
    id: str
    title: str
    kind: str
    path: str | None = None
    before: int | None = None  # revision at the baseline; None for an artifact that did not exist then
    after: int | None = None  # revision now
    changed: bool = True  # False: a new revision with the same text and content as at the baseline


class PhaseReceipt(BaseModel):
    phase: PhaseId
    title: str = ""  # filled by the orchestrator (the domain does not know wing titles)
    updated: list[ArtifactChange] = Field(default_factory=list)
    added: list[ArtifactChange] = Field(default_factory=list)
    removed: list[ArtifactChange] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.updated) + len(self.added) + len(self.removed)


class PhaseProgress(BaseModel):
    phase: PhaseId
    title: str = ""  # filled by the orchestrator
    state: PhaseChangeState
    status: PhaseStatus  # the phase's own status, for display
    updated: bool = False  # at least one artifact of the phase differs from the baseline


class ChangeProgress(BaseModel):
    phases: list[PhaseProgress]
    current: PhaseId | None = None
    started: bool = False  # something changed since the baseline, or a phase is no longer approved
    complete: bool = False  # started, and every phase is approved again
    done: int = 0
    total: int = 0  # phases this change moves (every state but `untouched`)


class NextStep(BaseModel):
    """What happens next in the current phase. `run`: `steps` are run in order (`action`, `label` and
    `input` repeat the first one). `approve`: the phase waits for approval and its gate is open.
    `input`: the agent asked something. `blocked`: `reason` says what the developer has to do."""

    phase: PhaseId
    title: str = ""
    kind: NextKind
    action: str | None = None
    label: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    steps: list[ChangeStep] = Field(default_factory=list)
    reason: str | None = None


class ChangeView(BaseModel):
    """One change request with everything the UI shows about it."""

    number: int
    artifact_id: str
    kind: str
    request: str
    summary: str
    affected: list[str] = Field(default_factory=list)
    state: ChangeState
    started_at: datetime
    completed_at: datetime | None = None
    progress: ChangeProgress
    next: NextStep | None = None
    receipt: list[PhaseReceipt] = Field(default_factory=list)


class OpenChange(BaseModel):
    """The change in progress, small enough for the project view."""

    number: int
    done: int
    total: int
    next_phase: PhaseId | None = None


def digest(artifact: Artifact) -> str:
    raw = json.dumps({"text": artifact.text, "content": artifact.content}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def take_baseline(artifacts: Iterable[Artifact]) -> dict[str, BaselineEntry]:
    """Every artifact (latest revision, retired ones too) as it is right now."""
    return {a.id: BaselineEntry(revision=a.revision, retired=a.retired, digest=digest(a)) for a in artifacts}


def receipt(baseline: dict[str, BaselineEntry], artifacts: Iterable[Artifact], phases: list[PhaseId]) -> list[PhaseReceipt]:
    """Per phase (all of `phases`, in order): what differs from the baseline. An artifact that was added
    and retired again since the baseline is left out."""
    found = {ph: PhaseReceipt(phase=ph) for ph in phases}
    for a in sorted(artifacts, key=lambda a: a.id):
        if a.phase not in found:
            continue
        was = baseline.get(a.id)
        existed = was is not None and not was.retired
        entry = ArtifactChange(id=a.id, title=a.title, kind=a.kind.value, path=a.path, before=was.revision if existed and was else None, after=a.revision)
        if not existed and not a.retired:
            found[a.phase].added.append(entry)
        elif existed and a.retired:
            found[a.phase].removed.append(entry)
        elif existed and was is not None and a.revision != was.revision:
            entry.changed = not was.digest or digest(a) != was.digest
            found[a.phase].updated.append(entry)
    return list(found.values())


def progress(
    project: Project, phases: list[PhaseId], baseline: dict[str, BaselineEntry], artifacts: Iterable[Artifact], first_step: ChangeStep | None
) -> ChangeProgress:
    """Where the change stands. Before anything happened, the phase of the first step is current and
    everything that depends on it waits. Afterwards the first phase that is not approved is current."""
    touched = {r.phase for r in receipt(baseline, artifacts, phases) if r.count}
    approved = {ph for ph in phases if project.status(ph) is PhaseStatus.APPROVED}
    started = bool(touched) or len(approved) < len(phases)
    states: dict[PhaseId, PhaseChangeState] = {}
    if not started:
        current = first_step.phase if first_step is not None and first_step.phase in phases else (phases[0] if phases else None)
        behind = set(project.dependants(current)) if current is not None else set()
        for ph in phases:
            states[ph] = "current" if ph is current else "waiting" if ph in behind else "untouched"
    else:
        current = next((ph for ph in phases if ph not in approved), None)
        for ph in phases:
            if ph in approved:
                states[ph] = "done" if ph in touched else "untouched"
            else:
                states[ph] = "current" if ph is current else "waiting"
    entries = [PhaseProgress(phase=ph, state=states[ph], status=project.status(ph), updated=ph in touched) for ph in phases]
    return ChangeProgress(
        phases=entries,
        current=current,
        started=started,
        complete=started and current is None,
        done=sum(e.state == "done" for e in entries),
        total=sum(e.state != "untouched" for e in entries),
    )


def next_step(
    state: ChangeProgress, project: Project, first_step: ChangeStep | None, refresh: list[ChangeStep], approval_problem: str | None, title: str = ""
) -> NextStep | None:
    """The next step of the change, None when it is complete. `refresh` is how the current phase's wing
    brings its output up to date, `approval_problem` what its gate says right now."""
    ph = state.current
    if ph is None:
        return None
    name = title or ph.value
    entry = next(e for e in state.phases if e.phase is ph)
    status = project.status(ph)
    if status is PhaseStatus.NEEDS_INPUT:
        return NextStep(phase=ph, title=title, kind="input", reason=f"{name} has open questions. Answer them in the phase, then continue.")
    if first_step is not None and first_step.phase is ph and not entry.updated:
        return _run(ph, title, [first_step])
    if status is PhaseStatus.DRAFT:
        if approval_problem:
            return NextStep(phase=ph, title=title, kind="blocked", reason=approval_problem)
        return NextStep(phase=ph, title=title, kind="approve", label="Approve")
    if not refresh:
        return NextStep(phase=ph, title=title, kind="blocked", reason=f"{name} has no automatic update step. Update it in the phase, then continue.")
    return _run(ph, title, refresh)


def _run(phase: PhaseId, title: str, steps: list[ChangeStep]) -> NextStep:
    first = steps[0]
    return NextStep(phase=phase, title=title, kind="run", action=first.action, label=first.label, input=first.input, steps=steps)


def receipt_markdown(found: list[PhaseReceipt], titles: dict[PhaseId, str] | None = None) -> str:
    """The receipt as text, for the change artifact (`maintenance/change-<n>.md`)."""
    lines: list[str] = []
    for r in found:
        if not r.count:
            continue
        lines.append(f"### {(titles or {}).get(r.phase) or r.title or r.phase.value}")
        for a in r.updated:
            same = "" if a.changed else " (same content)"
            lines.append(f"- updated {a.path or a.title}: revision {a.before} -> {a.after}{same}")
        lines += [f"- added {a.path or a.title} (revision {a.after})" for a in r.added]
        lines += [f"- removed {a.path or a.title}" for a in r.removed]
        lines.append("")
    return "\n".join(lines).rstrip() or "No artifact changed."
