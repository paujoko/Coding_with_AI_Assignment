# P7 Maintenance and consistency (planned)

**Requirement (PDF, P7):** the developer returns with a change request, bug report or new requirement; the change propagates through requirements, diagrams, code, tests and deployment. Diagrams stay aligned with code, including detecting drift after hand edits and offering to fix it in either direction.

**What already exists:** phase-level propagation. A new revision of any artifact marks every downstream phase stale (`Project.mark_changed`), and the UI shows it.

**Suggested design**

- Fine-grained impact analysis on the trace graph: a change to REQ-004 touches exactly the diagrams, files and tests whose `covers` contain REQ-004.
- Drift detector (deterministic): parse the Python code with `ast` into classes, attributes and methods; parse the PlantUML class diagram; diff the two. The LLM only proposes how to repair (update diagram from code, or code from diagram); the developer picks the direction.
- Agents: `impact_analyst` (classifies a change request and plans the update), `sync` (applies the repair).
- Actions: `change_request {text}`, `check_drift`, `repair {direction}`.

**Grading hooks:** C2 (main criterion), C5.
