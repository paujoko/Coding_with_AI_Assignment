# Wings foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running skeleton of the Wings environment: all seven phases in the pipeline, P1 and P2 working end to end on a mock LLM, architecture rules enforced by tests, documentation folders in place.

**Architecture:** Ports and adapters. `domain` (pure rules) <- `application` (ports, phase contract, orchestrator) <- `phases` (one package per wing) and `adapters` (store, LLM, renderer) <- `bootstrap` (composition root) <- `api` / `cli`. React frontend talks to the FastAPI API only.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, httpx, pytest; React 18, TypeScript, Vite, Vitest, Testing Library.

**Spec:** `docs/process/specs/2026-11-09-foundation-design.md`

**Execution:** Native (Claude implements in this session, then one fresh reviewer checks the whole result). Chosen because Paul asked for the full pipeline in one go and the tasks depend tightly on each other's interfaces.

## Global Constraints

- No module under `wings/phases/<x>/` imports another phase package or anything in `wings/adapters`, `wings/api`, `wings/bootstrap`.
- `wings/domain` imports only the standard library, Pydantic and `wings.domain`.
- `wings/application` imports only the standard library, Pydantic, `wings.domain` and `wings.application`.
- `wings/adapters` never imports `wings.phases`, `wings.api`, `wings.bootstrap`.
- `wings/api` never imports `wings.adapters` or `wings.phases`.
- Default LLM provider is `mock`; no test performs network I/O.
- All timestamps UTC ISO 8601.
- Docs in English, no em-dashes.
- Backend port 8810, frontend dev port 5190 (unused in `.claude/launch.json`).

## Review Focus

- Running an action on a locked phase must return HTTP 409 with a readable reason, not a 500.
- An LLM reply that is not valid JSON for the schema must be retried once, then surface as a phase error event and HTTP 502, leaving the artifact unchanged.
- A developer edit of an approved requirements artifact must mark design and every later phase that was draft or approved as stale.
- Unknown project, phase or action IDs must return 404.
- Project names with spaces or umlauts must produce a safe workspace folder name (slug) and still display the original name.

---

### Task 1: Backend package and architecture test

**Files:**
- Create: `backend/pyproject.toml`, `backend/src/wings/__init__.py`, empty `__init__.py` in `domain`, `application`, `phases`, `adapters`, `api`
- Test: `backend/tests/architecture/test_layers.py`

**Interfaces:**
- Produces: `RULES: dict[str, set[str]]` (layer -> forbidden import prefixes) inside the test; the test walks every `.py` under `src/wings` with `ast` and fails listing `file:line imports X`.

- [ ] Write `test_layers.py` with the rules from Global Constraints plus `test_phases_do_not_import_each_other`.
- [ ] Create venv `backend/.venv`, install `-e .[dev]`, run `pytest tests/architecture -q`. Expected: PASS (empty packages).
- [ ] Commit `chore: backend skeleton with enforced layer rules`.

### Task 2: Domain: phases, project state machine

**Files:**
- Create: `backend/src/wings/domain/phases.py`, `domain/project.py`, `domain/errors.py`
- Test: `backend/tests/domain/test_project.py`

**Interfaces:**
- Produces: `PhaseId(StrEnum)` with the seven IDs; `PhaseStatus(StrEnum)`; `PhaseState(BaseModel)`; `Project(BaseModel)` with `id, name, created_at, phases: dict[PhaseId, PhaseState]`; methods `Project.new(name, dependencies: dict[PhaseId, list[PhaseId]]) -> Project`, `can_run(phase) -> bool`, `set_status(phase, status)`, `approve(phase)`, `reopen(phase)`, `mark_changed(phase) -> list[PhaseId]` (returns phases made stale); `slugify(name) -> str`; errors `DomainError`, `PhaseLockedError`, `InvalidTransitionError`.

- [ ] Tests: new project has P1 `ready`, the rest `locked`; `approve(requirements)` makes design `ready`; `approve` on a phase without output raises `InvalidTransitionError`; `mark_changed(requirements)` after design approved returns `[design]` and leaves locked phases locked; transitive staleness across three phases; `slugify("Büro Buchung 2")` == `"buero-buchung-2"`.
- [ ] Implement; run `pytest tests/domain -q`; commit `feat(domain): project phase state machine`.

### Task 3: Domain: artifacts, messages, events, trace graph

**Files:**
- Create: `domain/artifacts.py`, `domain/conversation.py`, `domain/events.py`, `domain/trace.py`
- Test: `tests/domain/test_trace.py`

**Interfaces:**
- Produces: `ArtifactKind(StrEnum)` (`requirements`, `diagram`, plus later kinds); `Artifact(BaseModel)` fields `id, kind, phase, revision, title, content: dict, covers: list[str], path: str|None, author, created_at`; `Message(BaseModel)` `phase, role, text, created_at`; `Event(BaseModel)` `seq, at, kind, phase|None, summary, data: dict`; `coverage(requirement_ids: list[str], artifacts: list[Artifact]) -> CoverageReport` with `covered: dict[str, list[str]]`, `uncovered: list[str]`, `unknown_refs: list[str]`.

- [ ] Tests: coverage lists uncovered IDs in input order; a diagram covering `REQ-099` that does not exist is reported in `unknown_refs`.
- [ ] Implement, run, commit `feat(domain): artifacts and trace coverage`.

### Task 4: Application: ports, phase contract, registry, structured LLM calls

**Files:**
- Create: `application/ports.py`, `application/phase.py`, `application/registry.py`, `application/structured.py`, `application/prompts.py`
- Test: `tests/application/test_structured.py`, `tests/application/test_registry.py`

**Interfaces:**
- Produces (ports, all `Protocol`): `LLMClient.complete(req: LLMRequest) -> LLMReply`; `ArtifactStore` (`save_project`, `load_project`, `list_projects`, `save_artifact(project_id, artifact) -> Artifact` assigning the next revision, `get_artifact`, `list_artifacts(project_id, phase=None)`, `artifact_history`, `append_message`, `list_messages`, `append_event`, `list_events(project_id, after)`); `DiagramRenderer.render_svg(source) -> str | None`.
- `LLMRequest(agent, system, messages: list[dict], tier: Literal["small","mid","frontier"])`, `LLMReply(text, model, usage: dict)`.
- `call_structured(llm, req, schema: type[T], retries=1) -> T`; raises `LLMOutputError` after retries.
- `ActionSpec(name, description, input_model)`, `PhaseContext(project, store, llm, renderer, log: Callable[[str, dict], None])`, `ActionOutcome(status: PhaseStatus, messages: list[str], artifacts: list[Artifact], data: dict)`, `PhaseModule` (abstract: `id, title, summary, requires, implemented, actions, run(action, payload, ctx)`), `PlannedPhase(PhaseModule)` with no actions.
- `PhaseRegistry(modules)`: `get(phase_id)`, `ordered()`, `dependencies() -> dict[PhaseId, list[PhaseId]]`, validates no unknown or cyclic requires.
- `load_prompt(package: str, name: str) -> str` via `importlib.resources`.

- [ ] Tests: structured call parses fenced JSON; retries once with the validation error appended, then raises; registry rejects a cycle.
- [ ] Implement, run, commit `feat(application): ports, phase contract, registry`.

### Task 5: Adapters

**Files:**
- Create: `adapters/fs_store.py`, `adapters/llm_mock.py`, `adapters/llm_openrouter.py`, `adapters/plantuml.py`, `adapters/mock_scripts/demo_todo.json`
- Test: `tests/adapters/test_fs_store.py`, `test_llm_openrouter.py`, `test_llm_mock.py`

**Interfaces:**
- `FileSystemStore(root: Path)` implements `ArtifactStore`; layout `root/<project_id>/project.json`, `events.jsonl`, `messages.jsonl`, `artifacts/<artifact_id>/r0001.json`, materialized files under `files/`.
- `ScriptedLLM(script: dict[str, list[str]])` returns replies per `agent` key in order, last reply repeats; `ScriptedLLM.from_file(path)`; records `calls`.
- `OpenRouterLLM(api_key, models: dict[tier, model_id], client: httpx.Client|None)`; POST `/api/v1/chat/completions`.
- `PlantUMLRenderer(jar: Path|None, server_url: str|None)`; returns `None` when neither is configured.

- [ ] Tests: store round trip and revision numbering; events `after` filter; OpenRouter request body and auth header via `httpx.MockTransport`; scripted mock order.
- [ ] Implement, run, commit `feat(adapters): filesystem store, LLM and renderer adapters`.

### Task 6: Orchestrator

**Files:**
- Create: `application/orchestrator.py`
- Test: `tests/application/test_orchestrator.py` (uses `FakePhase` defined in the test and `FileSystemStore(tmp_path)`)

**Interfaces:**
- `Orchestrator(registry, store, llm, renderer, clock)`: `create_project(name) -> Project`, `run_action(project_id, phase, action, payload: dict) -> ActionOutcome`, `approve(project_id, phase) -> Project`, `reopen(project_id, phase) -> Project`, `update_artifact(project_id, artifact_id, content: dict, title|None) -> Artifact`, `project(project_id)`.
- Errors: `NotFoundError`, `PhaseLockedError` (from domain), `ActionFailedError(message)`.

- [ ] Tests: locked phase raises `PhaseLockedError`; outcome artifacts saved and phase status set; new revision on an approved phase reopens it to `draft` and stales dependants; developer edit author is `developer`; every call writes events; LLM failure writes `phase.error` event and raises `ActionFailedError`.
- [ ] Implement, run, commit `feat(application): orchestrator with gates and staleness`.

### Task 7: P1 Requirements wing

**Files:**
- Create: `phases/requirements/__init__.py` (exports `MODULE`), `module.py`, `schema.py`, `prompts/system.md`, `prompts/discuss.md`
- Test: `tests/phases/test_requirements.py`

**Interfaces:**
- `RequirementsOutput(questions: list[Question], requirements: list[RequirementItem], summary: str)`; `RequirementItem(id, title, description, type: functional|non_functional, priority: must|should|could, acceptance_criteria: list[str])`.
- Actions `start`, `answer`, `revise`, `discuss` as in the spec. Requirement IDs are renumbered `REQ-001`... by the module, never trusted from the LLM.
- Artifact: kind `requirements`, id `requirements`, path `requirements.md` (rendered markdown).

- [ ] Tests: questions -> `needs_input` and no artifact; requirements -> `draft`, IDs renumbered; `discuss` returns text and no artifact.
- [ ] Implement, run, commit `feat(phases): requirements wing`.

### Task 8: P2 Design wing and planned wings P3 to P7

**Files:**
- Create: `phases/design/` (same layout), `phases/refinement|codegen|testing|deployment|maintenance/__init__.py` with `PlannedPhase` and a README stating the intended behaviour.
- Test: `tests/phases/test_design.py`

**Interfaces:**
- `DesignOutput(diagrams: list[DiagramItem], notes: str)`; `DiagramItem(name, kind: use_case|class|sequence|activity|component|deployment, plantuml, covers, rationale)`.
- Each diagram becomes artifact id `diagram-<slug(name)>`, path `design/<slug>.puml`; outcome `data["coverage"]` is the `CoverageReport`.
- Requires: design <- requirements; refinement <- design; codegen <- refinement; testing <- codegen; deployment <- testing; maintenance <- deployment.

- [ ] Tests: generate produces diagram artifacts and coverage; invalid PlantUML raises `ActionFailedError` path via `LLMOutputError`; registry of all seven validates.
- [ ] Implement, run, commit `feat(phases): design wing and planned wings`.

### Task 9: Bootstrap, API, CLI

**Files:**
- Create: `config.py`, `bootstrap.py`, `api/app.py`, `api/dto.py`, `api/routes.py`, `cli.py`
- Test: `tests/api/test_api.py`

**Interfaces:**
- `Settings.from_env()` (`WINGS_WORKSPACE_DIR`, `WINGS_LLM_PROVIDER`, `WINGS_MOCK_SCRIPT`, `OPENROUTER_API_KEY`, `WINGS_MODEL_SMALL|MID|FRONTIER`, `PLANTUML_JAR`, `PLANTUML_SERVER_URL`).
- `build_container(settings) -> Container` (`orchestrator`, `registry`, `store`, `renderer`, `settings`); `create_app(container) -> FastAPI`.
- Routes under `/api`: `GET health`, `GET phases`, `GET|POST projects`, `GET projects/{id}`, `POST projects/{id}/phases/{phase}/actions/{action}`, `POST .../approve`, `POST .../reopen`, `GET projects/{id}/artifacts`, `GET|PUT projects/{id}/artifacts/{aid}`, `GET projects/{id}/artifacts/{aid}/history`, `GET projects/{id}/artifacts/{aid}/svg`, `GET projects/{id}/messages`, `GET projects/{id}/events`, `GET projects/{id}/trace`.
- Error mapping: NotFound 404, PhaseLocked and InvalidTransition 409, ActionFailed 502, validation 422.
- CLI: `python -m wings.cli phases|create|status|run|approve`.

- [ ] Tests: the full P1 to P2 happy path through HTTP with the scripted mock; locked phase 409; unknown action 404; developer edit stales design.
- [ ] Implement, run all backend tests, commit `feat(api): HTTP API and CLI for targeted control`.

### Task 10: Frontend

**Files:**
- Create: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/api/{client,types}.ts`, `src/components/*`, `src/styles.css`
- Test: `frontend/src/components/PhaseRail.test.tsx`, `src/lib/status.test.ts`

**Interfaces:**
- Consumes the API of Task 9 via `/api` (Vite proxy to 8810).
- Layout: project picker; pipeline rail of the seven phases with status; phase workspace with conversation and action form on one side and artifact views on the other (requirements table with inline edit, diagram view with SVG or source, coverage report); activity log.

- [ ] Use the frontend-design skill for the visual direction.
- [ ] Tests: rail renders seven phases and marks locked ones as disabled; status label mapping.
- [ ] `npm run build` and `npm test` pass; commit `feat(frontend): pipeline workspace UI`.

### Task 11: Verification, review, docs

- [ ] Start both servers via the preview tool, run the todo scenario through the UI on the mock, screenshot.
- [ ] Dispatch one fresh reviewer on the whole repo; fix confirmed findings.
- [ ] Write `docs/code/*`, finish `docs/process/*` (session log, timeline, ADRs, AI usage, lessons), update `CLAUDE.md`.
- [ ] Commit `docs: code and process documentation for the foundation`.
