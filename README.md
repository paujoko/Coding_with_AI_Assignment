<img src="docs/assets/wings-mark.svg" width="56" alt="Wings mark: seven strokes, one per phase">

# Wings

An AI-assisted software engineering environment built for the course *Coding with AI* (University of St. Gallen, WS 2026, Prof. Dr. Guido Salvaneschi).

A developer describes the software they want. A team of LLM agents turns it into requirements, UML design, code, tests and a deployment, and keeps all of it consistent while the software changes. After every phase the developer sees the result, discusses it, edits it and approves it before the pipeline moves on.

The name comes from the project brief: code generation is the body of the bird, but it does not fly without the wings, everything before and after the code.

## Status

| Phase | Wing | State |
|---|---|---|
| P1 Requirements | left | working: clarifying questions, structured requirements with stable IDs, developer edits |
| P2 Design | left | working: PlantUML use case, class and sequence diagrams, requirement coverage check |
| P3 Design refinement | left | working: reviewer findings (code checks first), apply picked findings or comment on a diagram, the whole set is updated consistently |
| P4 Code generation | body | working: Python files from the refined design, every file parsed, classes compared with the class diagram |
| P5 Testing | right | working: pytest files named after requirements, run for real, results per requirement, a debugger that fixes a wrong test or sends the fix to the code |
| P6 Deployment | right | working: Dockerfile and start scripts, checked by code, program started once for real (Docker itself is not run) |
| P7 Maintenance | right | working: change requests with impact from the trace and a first step in the right phase; consistency check of design, code and tests |

Every phase runs on the free scripted demo model and on OpenAI or OpenRouter. All checks marked "by code" are deterministic: the model proposes, code verifies.

## Quick start

Requirements: Python 3.12 or newer, Node 20 or newer. Diagrams as pictures: open **Settings → Diagrams** and either use plantuml.com (one click, sends the diagram text to the public server) or download PlantUML to this computer (needs Java 17+). Graphviz is not needed.

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # on macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn wings.main:app --port 8810
```

```bash
cd frontend
npm install
npm run dev     # open http://localhost:5190
```

By default Wings runs on a **scripted demo model** (a to-do app scenario), so everything works without an API key and without cost. To use real models, open **Settings** at the bottom of the sidebar, choose OpenAI (or OpenRouter), paste your API key and press Save. Wings writes it to `.env` (git-ignored) and uses it at once; "Test connection" checks it. You can also edit `.env` by hand, see `.env.example`.

## How it is built

- Backend: Python, FastAPI, ports and adapters. Each phase is a self-contained package (a "wing") registered in a pipeline; an orchestrator enforces approval gates and marks later phases stale when something earlier changes. See `docs/code/architecture.md`.
- Agents: one or more LLM agents per wing (analyst, architect, ...), each with its own prompt file and model tier. They communicate through versioned artifacts, not with each other.
- Frontend: React and TypeScript. The seven phases are a checklist in the sidebar; each phase has a conversation, actions generated from the backend's schemas, editable results (requirements, diagrams, review findings, files, test results, checks, changes) and next-step buttons the agents propose; a traceability matrix links requirements to diagrams, code, tests and the latest test result. Visual system: `docs/code/design.md`.
- Agents use deterministic tools while they work (the architect checks PlantUML syntax, class/sequence consistency and requirement coverage; the coder parses its files and compares them with the design; the impact analyst looks up the trace).
- Generated code and tests run in a local sandbox (temporary folder, timeout, no secrets in the environment). See ADR 0013 for what it protects and what it does not.
- Wings is also an MCP server (`wings-mcp`): Claude Desktop, Claude Code or Cursor can drive every phase. See `docs/code/wings.md`.
- Developers can attach documents (text, Markdown, PDF, Word) to any message; the agents read their text.
- Every phase action is also reachable through the HTTP API (`/docs`) and the CLI (`wings run <project> <phase> <action>`, `wings attach <project> <file>`).

## Documentation

- `docs/code/`: how the code works (start with `docs/code/README.md`).
- `docs/process/`: how we built it, session by session, including which AI tools we used and what failed.
