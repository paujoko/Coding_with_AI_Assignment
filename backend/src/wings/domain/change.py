"""Change tracking: how far a change request got through the phases, computed by code.

When a change is requested, the maintenance wing records a baseline: every artifact id with the
revision it had at that moment. Everything else follows from comparing that baseline with the
artifacts and phase statuses of now:

- `progress`: per phase one of `done` (changed since the baseline, approved again and updated after
  everything upstream of it), `current` (the one to act on), `waiting` (behind the current one) or
  `untouched` (not part of the change and approved). A phase the change plans to move is never `untouched`:
  approving it without a new revision leaves it `current` or `waiting`.
- `next_step`: what to do in the current phase (run actions, approve, answer questions, or blocked).
- `receipt`: per phase the artifacts this change updated, added or removed. This is the evidence
  of which artefacts a change reached.

Pure functions, no I/O. The orchestrator runs them and closes a change (freezes progress and
receipt) once every planned phase is done.
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
    planned: list[PhaseId] = Field(default_factory=list)  # the phases this change has to move
    current: PhaseId | None = None
    started: bool = False  # something changed since the baseline, or a phase is no longer approved
    complete: bool = False  # started, and every planned phase is done (updated and approved again)
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


def planned_default(project: Project, phases: list[PhaseId], first_step: ChangeStep | None) -> list[PhaseId]:
    """The phases a change moves when the change record does not name them: the phase of the first step and
    everything that depends on it."""
    if first_step is None or first_step.phase not in phases:
        return list(phases)
    behind = {first_step.phase, *project.dependants(first_step.phase)}
    return [ph for ph in phases if ph in behind]


def _stamps(found: list[PhaseReceipt], artifacts: list[Artifact]) -> dict[PhaseId, datetime]:
    """Per phase when its newest changed or added artifact was saved (a phase that only removed files has none)."""
    saved = {a.id: a.created_at for a in artifacts}
    stamps: dict[PhaseId, datetime] = {}
    for r in found:
        times = [saved[c.id] for c in [*r.updated, *r.added] if c.id in saved]
        if times:
            stamps[r.phase] = max(times)
    return stamps


def progress(
    project: Project,
    phases: list[PhaseId],
    baseline: dict[str, BaselineEntry],
    artifacts: Iterable[Artifact],
    first_step: ChangeStep | None,
    planned: list[PhaseId] | None = None,
) -> ChangeProgress:
    """Where the change stands. `planned` are the phases the change has to move (default: the phase of the
    first step and what depends on it). A planned phase is `done` only when it received a new revision since
    the baseline, is approved again, and was updated after every phase upstream of it (so approving a stale
    phase without updating it, or after an earlier phase changed again, does not count). Every other
    unfinished phase waits behind the current one, the first of them. The change is complete when nothing is
    left to do."""
    arts = list(artifacts)
    found = receipt(baseline, arts, phases)
    touched = {r.phase for r in found if r.count}
    stamps = _stamps(found, arts)
    approved = {ph for ph in phases if project.status(ph) is PhaseStatus.APPROVED}
    moves = {ph for ph in (planned_default(project, phases, first_step) if planned is None else planned) if ph in phases}

    def settled(ph: PhaseId) -> bool:
        if ph not in touched or ph not in approved:
            return False
        stamp = stamps.get(ph)
        return stamp is None or all(stamps[up] <= stamp for up in project.upstream(ph) if up in stamps)

    open_phases = [ph for ph in phases if (not settled(ph) if ph in moves else ph not in approved)]
    current = open_phases[0] if open_phases else None
    started = bool(touched) or len(approved) < len(phases)
    states: dict[PhaseId, PhaseChangeState] = {}
    for ph in phases:
        if ph in open_phases:
            states[ph] = "current" if ph is current else "waiting"
        else:
            states[ph] = "done" if ph in touched else "untouched"
    entries = [PhaseProgress(phase=ph, state=states[ph], status=project.status(ph), updated=ph in touched) for ph in phases]
    return ChangeProgress(
        phases=entries,
        planned=[ph for ph in phases if ph in moves],
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
    if status is PhaseStatus.DRAFT and entry.updated:
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
