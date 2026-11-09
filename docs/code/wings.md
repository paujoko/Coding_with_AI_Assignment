# Wings: the phase contract and how to extend it

A wing is one phase of the pipeline. It lives in `backend/src/wings/phases/<name>/` and exposes `MODULE`, an instance of a `PhaseModule` subclass (`application/phase.py`).

## The contract

```python
class MyPhase(PhaseModule):
    id = PhaseId.TESTING                    # which phase
    title = "Testing"
    summary = "One sentence for the UI"
    requires = [PhaseId.CODEGEN]            # gates: these must be approved first

    actions -> list[ActionSpec]             # what the developer can ask for
    agents  -> list[AgentInfo]              # shown in the UI and the architecture docs
    run(action, payload, ctx) -> ActionOutcome
    apply_developer_edit(artifact, content, text) -> Artifact   # optional: validate and re-render hand edits
```

- `ActionSpec(name, label, description, input_model, message_field)`: `input_model` is a Pydantic model; the frontend builds the form from its JSON schema, the API validates against it. `message_field` names the input that is the developer's words (logged in the conversation).
- `PhaseContext` gives the wing everything it may use: `project`, `phase`, `store`, `llm`, `renderer`, `log(kind, summary, data)`, and helpers `artifacts(phase)` and `messages()`.
- `ActionOutcome(status, reply, artifacts, data)`: `status=None` leaves the phase status unchanged (used for discussions). Returned artifacts are saved as new revisions by the orchestrator, which then propagates staleness. The wing never saves directly.
- Raise `InvalidTransitionError` for "not possible right now" (409), `ValueError` for bad input (422). LLM failures are handled by the orchestrator.

## Agents inside a wing

`application/agent.py: LLMAgent(name, role, system_prompt, tier)`.

- `ask(ctx, turns, Schema)` returns a validated Pydantic object (one retry with the validation error).
- `chat(ctx, turns)` returns plain text (for discussions).
- Every call is logged as an `agent.llm_call` event with model, attempts, seconds and cost.
- Prompts live in `phases/<wing>/prompts/*.md` and are loaded with `load_prompt(__package__, "system.md")`. Keep them in files: they are versioned, reviewable and quotable in the report.
- `turns_from(ctx.messages())` turns the phase conversation into chat turns.

## Existing wings

| Wing | Agents (tier) | Actions | Artifacts |
|---|---|---|---|
| P1 `requirements` | analyst (mid) | start, answer, revise, discuss | `requirements` (content: summary, requirements, assumptions; text: requirements.md) |
| P2 `design` | architect (frontier) | generate, revise, discuss | `diagram-<slug>` per diagram (content: kind, rationale; text: PlantUML) |
| P3 to P7 | planned | none | see each package README |

## Add or deepen a wing: checklist

1. Read the wing's README in its package; it states what the course requires and a suggested design.
2. Replace the `PlannedPhase` class in `phases/<wing>/__init__.py` with a real module (`module.py`, `schema.py`, `prompts/`), following `phases/requirements/` as the example. Set `implemented` by inheriting from `PhaseModule` instead of `PlannedPhase`.
3. If the wing needs the outside world (run pytest, build Docker), add a **port** in `application/ports.py`, an **adapter** in `adapters/`, a field on `PhaseContext`, and wire it in `bootstrap.py`. Do not call subprocesses or HTTP from the wing itself.
4. New artifact kinds go into `ArtifactKind`; add their trace IDs to `defines`/`covers`.
5. Add a mock script entry for each new agent name in `adapters/mock_scripts/demo_todo.json` so the demo and tests run without API calls.
6. Tests: one test file in `tests/phases/` driving the wing through the orchestrator (see `tests/phases/test_design.py`).
7. Frontend: actions appear automatically. A new artifact kind needs a view component in `frontend/src/components/` and a branch in `PhaseWorkspace.tsx`.
8. Update this page and the wing's README; record the session in `docs/process/`.

## Targeted control

Every action of every wing can be triggered directly, without going through the UI:

```bash
wings run todo-app design revise feedback="Split TaskService into two classes"
curl -X POST localhost:8810/api/projects/todo-app/phases/design/actions/discuss \
     -H "Content-Type: application/json" -d '{"input": {"question": "Why a repository?"}}'
```

Gates still apply: a phase whose inputs are not approved answers 409.
