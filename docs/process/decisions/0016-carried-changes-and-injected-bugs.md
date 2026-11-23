# 0016 Changes carried through step by step, and tests judged by injected bugs

- Date: 2026-11-23
- Status: accepted
- Decided by: Paul with Claude Code (Fable 5.2), session s06

## Context

Two grading criteria were only half shown. C2 asks that a change "propagates through all the artefacts" and that the demo shows "which artefacts were updated". Wings marked later phases out of date and left the developer to find their way through six of them; nothing listed what a change touched. C7 asks to "show a generated test failing on an injected bug"; the plan was to edit a line by hand in the demo.

## Decision

1. **A change request records a baseline** (every artifact id and revision). Progress, the next step and a receipt (per phase: updated with revision before and after, added, removed) are pure functions in `domain/change.py`.
2. **`POST /projects/{id}/changes/{n}/advance` runs exactly one phase** through the normal `run_action` path; each wing names its own refresh actions (`PhaseModule.refresh_step`), so the orchestrator knows no action names. With `approve: true` it approves the phase only when the wing reported a draft and the wing's own approval gate is open, and logs that it did so at the developer's request. It stops with a reason at open questions, failed checks and failed actions. When the change is complete, Maintenance runs its consistency check (code only).
3. **The UI defaults to one step at a time**; "Carry it through" is an explicit choice that says it approves steps whose code checks pass.
4. **Injected bugs**: the testing action `probe` makes up to 20 single-line mutants of the generated code with `ast` (domain, no subprocess), runs the generated tests against each in the sandbox, and reports caught, survived and not counted (collection errors, timeouts). No model is called. The report goes out of date like the test report and never counts as trace coverage. It does not change the phase's status (`ActionOutcome.changes_phase = False`).

Rejected:

- **Run all phases in one request.** Minutes with a real model, no progress, no way to stop between steps.
- **Approve without the wing's gate.** It would let a red test run or a failed deployment check through.
- **Count a timeout as a caught bug.** A loaded machine would raise the score.

## Consequences

- The demo can show a requirement change reaching code, tests and deployment with a list of revisions, and a test suite judged by bugs Wings planted itself.
- Limits: equivalent mutants are not detected, so the score is a signal, not a proof. With the scripted mock, a surviving bug cannot be closed by a new test (the tester returns the same script). Approval on the developer's behalf trusts the code gates; it does not judge the quality of a revised diagram.
