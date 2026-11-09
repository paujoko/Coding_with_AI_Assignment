# Wings

An AI-assisted software engineering environment built for the course *Coding with AI* (University of St. Gallen, WS 2026, Prof. Dr. Guido Salvaneschi).

A developer describes the software they want. A team of LLM agents turns it into requirements, UML design, code, tests and a deployment, and keeps all of it consistent while the software changes. After every phase the developer sees the result, discusses it, edits it and approves it before the pipeline moves on.

The name comes from the project brief: code generation is the body of the bird, but it does not fly without the wings, everything before and after the code.

## Status

| Phase | Wing | State |
|---|---|---|
| P1 Requirements | left | working: clarifying questions, structured requirements with stable IDs, developer edits |
| P2 Design | left | working: PlantUML use case, class and sequence diagrams, requirement coverage check |
| P3 Design refinement | left | planned |
| P4 Code generation | body | planned |
| P5 Testing | right | planned |
| P6 Deployment | right | planned |
| P7 Maintenance | right | planned (phase-level change propagation already works) |

## Quick start

Requirements: Python 3.12 or newer, Node 20 or newer. Optional: Java 17 and `plantuml.jar`, or a PlantUML server, to see diagrams as pictures.

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

By default Wings runs on a **scripted mock LLM** (a to-do app scenario), so everything works without an API key and without cost. To use real models, copy `.env.example`, set `WINGS_LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`, and pick models per tier.

## How it is built

- Backend: Python, FastAPI, ports and adapters. Each phase is a self-contained package (a "wing") registered in a pipeline; an orchestrator enforces approval gates and marks later phases stale when something earlier changes. See `docs/code/architecture.md`.
- Agents: one or more LLM agents per wing (analyst, architect, ...), each with its own prompt file and model tier. They communicate through versioned artifacts, not with each other.
- Frontend: React and TypeScript. The pipeline is drawn as a wingspan; each phase has a conversation, actions generated from the backend's schemas, and editable artifacts.
- Every phase action is also reachable through the HTTP API (`/docs`) and the CLI (`wings run <project> <phase> <action>`).

## Documentation

- `docs/code/`: how the code works (start with `docs/code/README.md`).
- `docs/process/`: how we built it, session by session, including which AI tools we used and what failed.
