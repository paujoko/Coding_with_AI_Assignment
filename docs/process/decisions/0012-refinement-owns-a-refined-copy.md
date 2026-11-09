# 0012 Refinement owns a refined copy of the design; wings hand work over as next steps

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) while building P3 to P7 on Paul's instruction ("mache weiter mit der ganzen Implementierung")

## Context

P3 changes the diagrams P2 made. Two options: P3 writes new revisions of P2's `diagram-*` artifacts, or P3 keeps its own copies. Writing P2's artifacts from P3 would break the rule that a wing only saves its own artifacts, and every refinement would mark P3 itself stale (a new revision in P2 makes everything after P2 stale). Later wings must also know which design to build on.

A related question came up in P5 and P7: the debugger finds a bug in the code, the impact analyst knows a change starts in the requirements. Wings are independent and must not call each other.

## Decision

- P3 saves the refined set as `refined-<slug>` artifacts in its own phase (`refinement/<slug>.puml`). P2's diagrams stay as approved.
- `PhaseContext.current_design()` returns P3's diagrams if there are any and they are newer than P2's latest change, else P2's. P4 to P7 read the design only through it. (Amended after the independent review of round 7: the first version preferred P3's copy even after P2 changed, so a design change never reached the later wings.)
- The trace view and the impact analysis leave out P2 diagrams once P3 has copies (`domain/trace.py: without_superseded`), so a reader sees one design, not two.
- A wing proposes work for another wing as `data.next_actions` (`{label, phase, action, input}`). The UI shows a button; the developer carries the step over and sends it. The orchestrator runs it like any other action, gates included.

## Consequences

- A refinement never makes P2 stale and never loses P2's approved state; a P2 revision still makes the refinement stale, as it should.
- Two places hold diagrams. The design view of P3 is titled "Refined design" to make that visible.
- Cross-wing handovers are visible and under the developer's control, at the cost of one extra click. No wing imports another; the architecture test stays as it is.
