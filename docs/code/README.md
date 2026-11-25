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
      adapters/      filesystem store, mock, OpenAI, OpenRouter and Anthropic LLMs, prices, PlantUML renderer, sandbox, the developer's project folder, mock scripts
      api/           FastAPI app and DTOs
      bootstrap.py   composition root: the list of wings and the choice of adapters
      config.py      settings from environment variables
      main.py        ASGI entry (uvicorn wings.main:app)
      cli.py         `wings` command line
      mcp_server.py  `wings-mcp`: Wings as an MCP server for Claude Desktop, Claude Code, Cursor
    tests/           architecture, domain, application, adapters, phases, api
  frontend/
    src/api/         typed client and DTO types
    src/components/  Sidebar (switcher, step checklist), PhaseWorkspace, Conversation, Composer, views (requirements, design, trace, activity)
    src/lib/         status labels and hints, mark geometry, formatting
  docs/assets/       logo (the Wings mark)
  docs/code/         this folder
  docs/process/      how we worked (append-only)
  workspaces/        runtime data, one folder per project, and wings_llm.log with every prompt and reply (git-ignored)
```

## Ports and local URLs

| What | Where |
|---|---|
| Backend API | http://localhost:8810/api, interactive docs at http://localhost:8810/docs |
| Frontend dev server | http://localhost:5190 (proxies `/api` to 8810; set `WINGS_BACKEND_PORT` for a backend on another port, e.g. `WINGS_BACKEND_PORT=8861 npx vite --port 5221` for a second pair of servers) |
| Preview tool entries (ClaudeBrain) | `wings-backend`, `wings-frontend` in `.claude/launch.json` of the ClaudeBrain root |
| Diagrams | `PLANTUML_JAR=/path/plantuml.jar` (Java needed, Graphviz optional; a path that no longer exists falls back to `tools/plantuml.jar`) or `PLANTUML_SERVER_URL` |
| Default project folders | `WINGS_PROJECTS_DIR` (default `~/WingsProjects`): a project created without a folder gets `<that>/<project slug>` |

## Current state in one paragraph

All seven wings are implemented and run end to end on the scripted mock (a to-do app): requirements with stable IDs; design with the PlantUML diagrams the developer chooses (kinds, simple or detailed) and coverage; refinement with reviewer findings and a refined copy of the design; code generation checked against the class diagram; tests (focused or thorough, capped by code; pytest, and Node's built-in runner for JavaScript logic) run for real on the developer's click with results per requirement and a count of the requirements a passing test verifies, said at the gate; deployment files checked by code with a real smoke run; maintenance with change requests (impact computed from the trace) and a consistency check (drift, per-requirement progress). Phase-level change propagation marks later phases stale and names the cause; the gates walk the developer through every update. Agents call deterministic tools; Wings is also an MCP server. OpenAI, OpenRouter and Claude (Anthropic API, ADR 0021) work through Settings; a real run on OpenRouter with `deepseek/deepseek-v4.1-flash-1017` (the course model) passed all seven wings on 2026-11-09 in about 11 minutes for about 0.08 USD (session s03). Each project can have its own folder on the developer's computer: Wings writes every file there after each step, notices hand edits, and imports them on request as developer revisions, after which design and code are compared again (ADR 0015, session s04). Known limits: generated logic is Python, and JavaScript only where it must run in the browser; JavaScript is tested with Node (ADR 0020) but not compared with the design, and page scripts are not tested; the sandbox is not a security boundary; Docker is not run; the drift check compares classes, public methods, inheritance and unambiguous attributes, not associations, types or parameter lists.
