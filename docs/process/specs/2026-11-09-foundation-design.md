# Foundation design: the Wings environment skeleton

Date: 2026-11-09. Author: Claude Code (Opus 5.5) on Paul's instruction. Status: approved for implementation by Paul's instruction to "lay the foundation" (the decisions below are Claude's calls unless marked otherwise; Paul can overturn any of them).

## Intent

The course project (see the project requirements PDF, sections 2 to 5) asks for a multi-agent, LLM-based environment that takes a developer from a vague idea through requirements, UML design, design refinement, code, tests, deployment and maintenance. Grading is mostly on the "wings": everything before and after code generation (criteria C1 to C7).

This first session builds the **skeleton** the two team members will extend for the remaining weeks. It must make three things easy:

1. Adding or deepening a wing (phase) without touching the others.
2. Triggering any phase action directly ("targeted control"), from the UI, the HTTP API or a CLI.
3. Seeing, editing and approving every artifact before the pipeline moves on (the developer stays in control).

## Goals

- A running backend and frontend with all seven phases visible in the pipeline.
- P1 Requirements and P2 Design implemented end to end against a mock LLM, including clarifying questions, approval gates, developer edits and discussion.
- P3 to P7 registered as planned phases with their own packages, so each can be implemented independently.
- Change propagation at phase level: editing or revising an approved artifact marks every downstream phase as stale.
- Stable trace IDs (REQ-001 ...) and a trace graph with a deterministic coverage check (which requirements no diagram covers).
- Architecture rules enforced by a test, not by prose.
- Two documentation folders: `docs/code/` (how the code works, current truth) and `docs/process/` (how we worked, append-only, for the presentation and the individual report).

## Non-goals for this session

- Real implementations of P3 to P7 (refinement loop, code generation, testing, deployment, drift detection).
- MCP servers. Tools are plain ports for now; the port shape is chosen so that wrapping them as MCP servers later is mechanical.
- Authentication, multi-user, cloud deployment.
- Real LLM calls. AI coding agents never trigger paid model calls (Paul's rule); the mock provider is the default and the OpenRouter adapter is tested against a fake HTTP transport only.

## Anti-goals (would make it a failure even if it runs)

- A fixed script with a few prompts in it (criterion C4 forbids exactly this).
- Phases that import each other. Wings must stay independent and talk only through artifacts.
- Hidden LLM decisions where a deterministic check is possible (coverage, drift, test results).

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Name | **Wings** | The requirements PDF calls everything around code generation "the wings". |
| Backend | Python 3.14, FastAPI, Pydantic v2, httpx, pytest | Python's `ast` module makes drift detection on generated Python code cheap later; FastAPI gives an OpenAPI description of the targeted-control API for free. |
| Architecture | Ports and adapters (hexagonal) with a phase plugin registry | See ADR 0001. |
| Frontend | React 18, TypeScript, Vite, Vitest | Chat plus artifact views is all the requirements ask for (section 6). |
| UML notation | PlantUML source, rendered to SVG by a backend port | Covers all UML diagram kinds the PDF names (use case, class, sequence, activity, component, deployment); Mermaid has no use case diagram. See ADR 0003. |
| LLM access | One `LLMClient` port; adapters: scripted mock (default) and OpenRouter (OpenAI-compatible) | The PDF warns against a single fragile API key; OpenRouter gives small, mid and frontier models behind one key. See ADR 0004. |
| Storage | One workspace folder per showcase project: JSON state, append-only event log, artifact revisions as JSON, plus human-readable materialized files (`requirements.md`, `design/*.puml`) | Simple, diffable, no database to run in the demo. |
| Agent communication | Blackboard: agents read and write artifacts through the store; the orchestrator (manager pattern) decides who runs | Matches the manager pattern from the agents lecture; keeps wings decoupled. |
| Live updates | Polling the activity log (`/events?after=n`) | Robust and good enough for a 12 minute demo; SSE can replace it later behind the same endpoint shape. |

## Domain model (summary)

- **PhaseId**: `requirements`, `design`, `refinement`, `codegen`, `testing`, `deployment`, `maintenance` (P1 to P7).
- **PhaseStatus**: `locked`, `ready`, `needs_input`, `draft`, `approved`, `stale`.
- **Project**: id, name, phase states. Rules: a phase can run only when every phase it requires is `approved`; approving a phase unlocks its dependants; a new revision of an artifact owned by an approved or draft phase turns every transitive dependant that is `draft` or `approved` into `stale`.
- **Artifact**: id, kind, owning phase, revision number, structured content (JSON), materialized path, `covers` (trace IDs it implements), author (`agent:<name>` or `developer`).
- **Trace IDs**: requirements `REQ-001`; diagrams reference requirement IDs in `covers`. Later wings add class and test IDs.
- **Message**: phase, role (`developer`, `agent`, `system`), text, timestamp.
- **Event**: sequence number, timestamp, kind, phase, summary. This is the "system explains what it is doing" log (criterion C3).

## Phase module contract

Every wing is one package under `wings/phases/<name>/` exposing a `PhaseModule`:

- `id`, `title`, `summary`, `requires: list[PhaseId]`, `implemented: bool`
- `actions: list[ActionSpec]` (name, description, input schema as a Pydantic model)
- `run(action, payload, ctx) -> ActionOutcome`

`ctx` (`PhaseContext`) gives the module the ports it may use: artifact store, LLM, renderer, event publisher, project snapshot. A module never imports another module or an adapter. The registry lists modules in pipeline order; the orchestrator owns gates, approvals, staleness and logging.

## P1 Requirements behaviour

- `start {description}`: the agent either returns clarifying questions (status `needs_input`) or a structured requirements set (status `draft`).
- `answer {answers}`: the developer answers open questions; the agent produces requirements or more questions.
- `revise {feedback}`: new revision from feedback.
- `discuss {question}`: answer only, no artifact change.
- Developer edits through the generic artifact update endpoint create a new revision authored by `developer`.

## P2 Design behaviour

- `generate`: from the approved requirements, produce a design bundle (at least use case and class diagrams) with rationale and `covers`. Fails with a clear message if a diagram is not valid PlantUML (`@startuml` ... `@enduml`).
- `revise {feedback}` and `discuss {question}` as in P1.
- A deterministic coverage report (requirements not covered by any diagram) is returned with every result and shown in the UI.

## Risks and open points

- Python 3.14 is new; if a dependency lacks wheels, fall back to 3.12 (installed on the machine).
- PlantUML rendering needs either a local `plantuml.jar` (Java 17 is installed) or a PlantUML server URL. Without either, the UI shows the diagram source. Getting one of them running is a step for Paul.
- The team partner has not seen this design yet.
