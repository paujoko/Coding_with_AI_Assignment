# P7 Maintenance and consistency

**Requirement (PDF, P7):** the developer returns with a change request, bug report or new requirement; the change propagates through requirements, diagrams, code, tests and deployment. Diagrams stay aligned with code, including detecting drift after hand edits and offering to fix it in either direction.

**How it works**

- `change {request}`: the `impact_analyst` (mid) classifies the request (`bug`, `change`, `new_requirement`), names the affected REQ ids after looking them up with the `trace_impact` tool, and writes the instruction for the first phase and a plan. Code drops ids that do not exist and computes from `covers` which diagrams, files and tests each requirement touches. Artifact `change-<n>` (`maintenance/change-<n>.md`; it does not count as coverage).
- The first step is a next action: "Update the requirements" (requirements `revise` with the instruction) or, for a bug, "Send the fix to Code generation". Running it makes every later phase stale.
- **Tracking, computed by code** (`domain/change.py`): the change artifact records a baseline (`content.baseline`: every artifact id with revision, retired flag and fingerprint) and the first step (`content.first_step`). From it the orchestrator computes the progress per phase (`done`, `current`, `waiting`, `untouched`), the next step, and the receipt: which artifacts the change updated, added or removed, per phase. `GET /projects/{id}/changes` shows all of it; the project view carries `open_change`.
- **Carrying it through**: `POST /projects/{id}/changes/{n}/advance` (CLI `wings advance`, MCP `advance_change`) runs one phase per call: the first step, later each wing's own `refresh_step`, through the ordinary action path with every gate. If asked to, it approves the phase on the developer's behalf when the wing's gate is open, and the log says so. It stops with a reason on open questions, a failed gate (red tests, failed deployment check) or a failed action. The developer can also do any step by hand in the phase; progress is computed from the artifacts either way.
- When every phase P1 to P6 is approved again, the change is closed: a new revision of `change-<n>` keeps the completion time, the frozen progress and the receipt (also as text under "Carried through" in `maintenance/change-<n>.md`).
- `check`: computed by code only. Class diagram against the Python classes (drift, files edited by hand) and per requirement: in a diagram, implemented, tested, latest test result. On drift, two next steps let the developer pick the direction: "Update the design from the code" (refinement `comment`) or "Update the code from the design" (codegen `revise`). Artifact `consistency` (`reports/consistency.md`).
- `discuss {question}`.

**Limits:** one change at a time (a change that was never started is `dropped` when the next one is requested); the receipt compares revisions of whole artifacts, it does not say which lines or diagram elements changed; a change is complete when the phases are approved again, P7 itself stays out of date until the next `check`; propagation is phase by phase; each wing regenerates or revises its whole output rather than patching single elements. Drift covers classes and public methods.

**Grading hooks:** C2 (main criterion), C5.
