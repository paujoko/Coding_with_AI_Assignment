"""The seven phases (wings and body) and the status a phase can be in."""

from enum import StrEnum


class PhaseId(StrEnum):
    REQUIREMENTS = "requirements"  # P1
    DESIGN = "design"  # P2
    REFINEMENT = "refinement"  # P3
    CODEGEN = "codegen"  # P4
    TESTING = "testing"  # P5
    DEPLOYMENT = "deployment"  # P6
    MAINTENANCE = "maintenance"  # P7


class PhaseStatus(StrEnum):
    LOCKED = "locked"  # some required phase is not approved
    READY = "ready"  # can run, has produced nothing yet
    NEEDS_INPUT = "needs_input"  # the agent asked the developer something
    DRAFT = "draft"  # output exists, waits for the developer's review
    APPROVED = "approved"  # developer accepted the output; dependants may use it
    STALE = "stale"  # output exists but an upstream phase changed since


# Statuses set by work done in the phase (not derived from the inputs like locked and ready).
WORKED_ON = frozenset({PhaseStatus.NEEDS_INPUT, PhaseStatus.DRAFT, PhaseStatus.APPROVED, PhaseStatus.STALE})

# Statuses with output that an upstream change can invalidate.
HAS_OUTPUT = frozenset({PhaseStatus.DRAFT, PhaseStatus.APPROVED})
