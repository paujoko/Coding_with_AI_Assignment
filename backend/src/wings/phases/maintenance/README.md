# P7 Maintenance and consistency

**Requirement (PDF, P7):** the developer returns with a change request, bug report or new requirement; the change propagates through requirements, diagrams, code, tests and deployment. Diagrams stay aligned with code, including detecting drift after hand edits and offering to fix it in either direction.

**How it works**

- `change {request}`: the `impact_analyst` (mid) classifies the request (`bug`, `change`, `new_requirement`), names the affected REQ ids after looking them up with the `trace_impact` tool, and writes the instruction for the first phase and a plan. Code drops ids that do not exist and computes from `covers` which diagrams, files and tests each requirement touches. Artifact `change-<n>` (`maintenance/change-<n>.md`; it does not count as coverage).
- The first step is a next action: "Update the requirements" (requirements `revise` with the instruction) or, for a bug, "Send the fix to Code generation". Running it makes every later phase stale; the gates then walk the developer through design, refinement, code, tests and deployment in order, and each phase says what changed upstream.
- `check`: computed by code only. Class diagram against the Python classes (drift, files edited by hand) and per requirement: in a diagram, implemented, tested, latest test result. On drift, two next steps let the developer pick the direction: "Update the design from the code" (refinement `comment`) or "Update the code from the design" (codegen `revise`). Artifact `consistency` (`reports/consistency.md`).
- `discuss {question}`.

**Limits:** propagation is phase by phase; each wing regenerates or revises its whole output rather than patching single elements. Drift covers classes and public methods.

**Grading hooks:** C2 (main criterion), C5.
