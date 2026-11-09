# P4 Code generation (planned)

**Requirement (PDF, P4):** code is generated from the approved design, not from the initial description. Classes from the class diagram appear in the code; interactions from sequence diagrams are visible in the calls. Keep it proportionate: least credit here.

**Suggested design**

- Agent: `coder` (mid tier is usually enough). Input: requirements, class diagram, sequence diagrams.
- Deterministic first step: parse the class diagram into a skeleton (class names, attributes, operations) and let the LLM fill bodies, so the structure follows the design by construction.
- Artifacts: one `source-<path>` artifact per file (kind to add: `SOURCE_FILE`), `covers` = REQ ids, plus a trace comment in the code (`# trace: REQ-003`).
- Generated projects are Python by default so the maintenance wing can compare code and diagrams with `ast`.

**Grading hooks:** C5 (requirement -> diagram -> code navigation), baseline for C6.
