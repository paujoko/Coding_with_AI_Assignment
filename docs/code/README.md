# Code documentation

What the code does **today** and where to find it. Updated in the same commit as the code it describes. For history and reasons, see `docs/process/`.

## Reading order for a new session

1. `architecture.md`: layers, dependency rules, request flow (10 minutes).
2. `domain-model.md`: phase states, artifacts, trace IDs.
3. `wings.md`: the contract every phase implements and how to add one.
4. Whatever you are about to touch: `llm.md`, `api.md`, `frontend.md` and `design.md` (any UI change), `testing.md`.

## Map of the repository

```
wings/
  backend/
    pyproject.toml
    src/wings/
      domain/        pure rules: phases, project state machine, artifacts, activity, trace coverage
      application/   ports (interfaces), phase contract, LLM agent, registry, orchestrator
      phases/        one package per wing (P1 to P7), each with module, schema, prompts/
      adapters/      filesystem store, mock and OpenRouter LLMs, PlantUML renderer, mock scripts
      api/           FastAPI app and DTOs
      bootstrap.py   composition root: the list of wings and the choice of adapters
      config.py      settings from environment variables
      main.py        ASGI entry (uvicorn wings.main:app)
      cli.py         `wings` command line
    tests/           architecture, domain, application, adapters, phases, api
  frontend/
    src/api/         typed client and DTO types
    src/components/  Sidebar, Pipeline, PhaseWorkspace, Conversation, Composer, views (requirements, design, trace, activity)
    src/lib/         status labels and hints, mark geometry, formatting
  docs/assets/       logo (the Wings mark)
  docs/code/         this folder
  docs/process/      how we worked (append-only)
  workspaces/        runtime data, one folder per project (git-ignored)
```

## Ports and local URLs

| What | Where |
|---|---|
| Backend API | http://localhost:8810/api, interactive docs at http://localhost:8810/docs |
| Frontend dev server | http://localhost:5190 (proxies `/api` to 8810) |
| Preview tool entries (ClaudeBrain) | `wings-backend`, `wings-frontend` in `.claude/launch.json` of the ClaudeBrain root |
| Diagrams | `PLANTUML_JAR=/path/plantuml.jar` (Java needed, Graphviz optional) or `PLANTUML_SERVER_URL` |

## Current state in one paragraph

P1 Requirements and P2 Design are implemented end to end on the scripted mock. P3 to P7 are registered as planned wings with a README each describing the intended behaviour. Phase-level change propagation works: any new revision marks dependent phases stale and records which phase caused it. The interface was redesigned in session s02 (see `design.md`): pipeline as a line of stations, inline system steps, traceability matrix, activity view, light and dark. Fine-grained impact analysis, drift detection, code generation, test execution and deployment are not built yet.
