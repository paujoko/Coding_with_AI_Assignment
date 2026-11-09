"""Project aggregate: owns the phase state machine.

Rules (see docs/code/domain-model.md):
- A phase can run only when every phase upstream of it (transitively) is approved.
- Approving needs output (draft or stale) and approved inputs.
- A change to a phase's output puts it back to draft and makes every
  transitive dependant with output (draft, approved) stale; open questions
  of a dependant are dropped (back to ready or locked).
- Locks are derived: a phase nobody worked on is locked or ready depending on
  its inputs, recomputed after every transition.
"""

import re
import unicodedata
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from wings.domain.errors import InvalidTransitionError, PhaseLockedError
from wings.domain.phases import HAS_OUTPUT, WORKED_ON, PhaseId, PhaseStatus

_TRANSLITERATE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"})


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name.translate(_TRANSLITERATE)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "project"


def utcnow() -> datetime:
    return datetime.now(UTC)


class PhaseState(BaseModel):
    status: PhaseStatus
    requires: list[PhaseId] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utcnow)
    stale_cause: PhaseId | None = None  # the upstream phase whose change made this one stale


class Project(BaseModel):
    id: str
    name: str
    created_at: datetime = Field(default_factory=utcnow)
    phases: dict[PhaseId, PhaseState]
    version: int = 0  # incremented by the store on every save; detects concurrent writers

    @classmethod
    def new(cls, name: str, dependencies: dict[PhaseId, list[PhaseId]], project_id: str | None = None) -> "Project":
        phases = {ph: PhaseState(status=PhaseStatus.LOCKED, requires=list(reqs)) for ph, reqs in dependencies.items()}
        project = cls(id=project_id or slugify(name), name=name, phases=phases)
        project._refresh_locks()
        return project

    # Queries

    def status(self, phase: PhaseId) -> PhaseStatus:
        return self.phases[phase].status

    def upstream(self, phase: PhaseId) -> list[PhaseId]:
        """Transitive requirements in pipeline order."""
        found: set[PhaseId] = set()
        frontier = set(self.phases[phase].requires)
        while frontier:
            found |= frontier
            frontier = {r for ph in frontier for r in self.phases[ph].requires} - found
        return [ph for ph in self.phases if ph in found]

    def inputs_approved(self, phase: PhaseId) -> bool:
        return all(self.status(dep) is PhaseStatus.APPROVED for dep in self.upstream(phase))

    def can_run(self, phase: PhaseId) -> bool:
        return self.inputs_approved(phase)

    def ensure_can_run(self, phase: PhaseId) -> None:
        if not self.can_run(phase):
            missing = [d.value for d in self.upstream(phase) if self.status(d) is not PhaseStatus.APPROVED]
            raise PhaseLockedError(f"Phase '{phase.value}' is locked: approve {', '.join(missing)} first.")

    def dependants(self, phase: PhaseId) -> list[PhaseId]:
        """Transitive dependants in pipeline order."""
        found: set[PhaseId] = set()
        frontier = {phase}
        while frontier:
            nxt = {ph for ph, st in self.phases.items() if frontier & set(st.requires)} - found
            found |= nxt
            frontier = nxt
        return [ph for ph in self.phases if ph in found]

    # Transitions

    def set_status(self, phase: PhaseId, status: PhaseStatus) -> None:
        self._set(phase, status)
        self._refresh_locks()

    def approve(self, phase: PhaseId) -> None:
        if self.status(phase) not in (PhaseStatus.DRAFT, PhaseStatus.STALE):
            raise InvalidTransitionError(
                f"Cannot approve '{phase.value}' while it is {self.status(phase).value}; it needs output to review."
            )
        self.ensure_can_run(phase)
        self.set_status(phase, PhaseStatus.APPROVED)

    def reopen(self, phase: PhaseId) -> None:
        if self.status(phase) is not PhaseStatus.APPROVED:
            raise InvalidTransitionError(f"Only an approved phase can be reopened; '{phase.value}' is {self.status(phase).value}.")
        self.set_status(phase, PhaseStatus.DRAFT)

    def mark_changed(self, phase: PhaseId) -> list[PhaseId]:
        """The phase produced a new revision. Returns the phases that became stale."""
        self._set(phase, PhaseStatus.DRAFT)
        dependants = self.dependants(phase)
        stale = [d for d in dependants if self.status(d) in HAS_OUTPUT]
        for dep in stale:
            self._set(dep, PhaseStatus.STALE)
            self.phases[dep].stale_cause = phase
        for dep in dependants:
            if self.status(dep) is PhaseStatus.NEEDS_INPUT:  # questions were about the old input
                self._set(dep, PhaseStatus.READY)
        self._refresh_locks()
        return stale

    # Internals

    def _set(self, phase: PhaseId, status: PhaseStatus) -> None:
        state = self.phases[phase]
        state.status = status
        state.updated_at = utcnow()
        if status is not PhaseStatus.STALE:
            state.stale_cause = None

    def _refresh_locks(self) -> None:
        for phase, state in self.phases.items():
            if state.status in WORKED_ON:
                continue
            wanted = PhaseStatus.READY if self.inputs_approved(phase) else PhaseStatus.LOCKED
            if state.status is not wanted:
                self._set(phase, wanted)
