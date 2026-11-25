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
    approval_problem(artifacts) -> str | None                   # optional: a gate checked by code before approval
    adopt_developer_file(path, text) -> Artifact | None         # optional: a file the developer created in their folder (ADR 0015)
    refresh_step(reason, artifacts) -> [(action, input), ...]   # optional: how this wing updates its output after an upstream change
```

- `ActionSpec(name, label, description, input_model, message_field)`: `input_model` is a Pydantic model; the frontend builds the form from its JSON schema, the API validates against it. `message_field` names the input that is the developer's words (logged in the conversation).
- `PhaseContext` gives the wing everything it may use: `project` (a copy), `phase`, `store` (read-only), `llm`, `renderer`, `sandbox` (may be None), `log(kind, summary, data)`, and helpers `artifacts(phase)`, `messages()`, `current_design()` and `documents()`. `messages()` already contains the developer's message of the current request (it is stored only if the action succeeds).
- `ActionOutcome(status, reply, artifacts, data)`: `status` may be `draft`, `needs_input` or `None` (unchanged, used for discussions); anything else is refused. Returned artifacts are saved as new revisions by the orchestrator, all or nothing, which then propagates staleness. The wing never saves directly.
- Artifact ids are lowercase slugs (`[a-z0-9][a-z0-9._-]*`, e.g. `source-app-models-py`); the real file location goes into `path` (relative, forward slashes). To remove an artifact, return it with `retired=True`.
- Raise `InvalidTransitionError` for "not possible right now" (409) and `InvalidInputError` for input the developer can fix (422). LLM failures and unexpected exceptions are turned into `ActionFailedError` (502) with a `phase.error` event by the orchestrator.

## Agents inside a wing

`application/agent.py: LLMAgent(name, role, system_prompt, tier)`.

- `ask(ctx, turns, Schema)` returns a validated Pydantic object (one retry with the validation error).
- `chat(ctx, turns)` returns plain text (for discussions).
- Every call is logged as an `agent.llm_call` event with model, attempts, seconds and cost.
- Prompts live in `phases/<wing>/prompts/*.md` and are loaded with `load_prompt(__package__, "system.md")`. Keep them in files: they are versioned, reviewable and quotable in the report.
- `turns_from(ctx.messages())` turns the phase conversation into chat turns.
- Chat replies are short: every prompt asks for at most two short sentences (about 40 words) for the text shown in the chat (`notes`, `summary`, `diagnosis`, discussion answers), stating the result and the one open point, never file contents or what the results panel shows. No schema limits length (a refusal would cost a model call); the wing cuts the text with `domain/text.py: brief` (at a sentence end, 320 characters) and lists computed lines with `short_list` (five, then a count). The full `notes` travel in `data.notes` of the message; details belong in the artifacts. `tests/phases/test_short_replies.py` checks every prompt file for the rule.
- `ask(..., tools=[...])` lets the agent call deterministic tools before it answers (see `llm.md`, Tools). Give an agent the checks that fit its job; add new tools to `application/tools.py` (generic) and keep them read-only.
- `document_turns(ctx, *phases)` adds the documents the developer attached in those phases (default: this phase). P1 reads its own, P2 reads P1's and its own. A new wing should prepend it to its turns.

## Existing wings

| Wing | Agents (tier), tools | Actions | Artifacts | Checked by code |
|---|---|---|---|---|
| P1 `requirements` | analyst (mid) | start, answer, revise, discuss | `requirements` (content: summary, requirements, assumptions; text: requirements.md) | IDs assigned and kept by code (ADR 0008) |
| P2 `design` | architect (frontier); check_plantuml, check_consistency, check_coverage (two tool rounds at the simple level, four at detailed) | generate {kinds, level, guidance}, revise, discuss | `diagram-<slug>` (content: kind, rationale, level; text: PlantUML) | PlantUML syntax, sequence vs class consistency, coverage; kinds drawn but not chosen and chosen but not drawn (`data.kinds`); approval needs every functional requirement in a diagram |
| P3 `refinement` | reviewer (frontier), refiner (frontier); the design tools | review, apply, comment, discuss | `review` (findings F1.. with severity, source reviewer or check, status open or applied); `refined-<slug>` diagrams (path `refinement/<slug>.puml`) | consistency and coverage problems become findings before the reviewer speaks; every refined set is checked again |
| P4 `codegen` | coder (mid); compare_with_design (at most two tool rounds) | generate, revise, discuss | `source-<slug>` (content: path, purpose, language; text: the file; path `app/<file>`; Python plus `.html`, `.css`, `.js`, `.svg` for web pages); `code-gaps` (requirements the coder says it did not meet) | every Python file parses (`ast`); classes, public methods, inheritance and unambiguous attributes against all class diagrams of the design (drift in the reply) |
| P5 `testing` | tester (mid, no tools), debugger (frontier); check_python for the debugger | generate {depth, guidance}, run, probe, explain, discuss | `test-<slug>` (tests under `tests/`); `test-gaps` (requirements the tests do not fully check); `test-report` (path `reports/test-results.md`); `test-strength` (path `reports/test-strength.md`) | the number of tests is capped by code (`schema.py: test_limit`, from the acceptance criteria; more is refused and retried); pytest runs for real in the Sandbox; JUnit XML gives the outcome per test and per requirement (`test_req_003_...`); declared gaps turn `passed` into `partial` or `not_met`; `probe` injects bugs into the code and counts which ones a test catches (no model) |
| P6 `deployment` | deployer (mid) | generate, check, revise, discuss | `deploy-<slug>` (Dockerfile, run.sh, run.ps1, DEPLOY.md); `deployment-check`; `run-guide` (kind `run_guide`, path `app/RUN.md`, so it lands next to DEPLOY.md in the developer's folder; content: `start_command`, `url`, `example_commands`, `stop_hint`, `checked`, `derived`) | COPY sources and `python -m` modules exist (`domain/deploy.py`); the start command and the examples of the run guide name a module or script the code has, else the check fails; the smoke command starts the program in the Sandbox, without a shell, fed `smoke_input` as standard input for interactive programs |
| P7 `maintenance` | impact_analyst (mid); trace_impact | change, check, discuss | `change-<n>` (kind, affected REQ ids, impact from the trace, plan, first step); `consistency` (path `reports/consistency.md`) | unknown REQ ids dropped; impact computed from `covers`; drift between the class diagrams and the code (classes, public methods, inheritance, unambiguous attributes); per requirement: diagram, code, tests, latest result |

Later wings read the design through `ctx.current_design()`: the refined diagrams of P3, unless P2 changed after the last refinement; then P2's diagrams until P3 refines again (ADR 0012, rule in `domain/trace.py: current_design`). The trace view and the impact analysis show only that design.

Approval gates checked by code (`approval_problem`): P2 can be approved only when every functional requirement appears in at least one diagram (s03: a design covering 1 of 11 could be approved); P5 can be approved only when the latest test run is green and newer than every source and test file; P6 only when the last deployment check passed and is newer than the deployment files and the code. A test report older than the code also stops counting as verification in the trace and the consistency check.

Target platform (s03): Wings builds Python 3.12 programs with the standard library, either for the command line or as a local web app (a `http.server` that serves HTML, CSS and JavaScript and keeps the logic in Python). The analyst, architect, coder, tester and deployer prompts all say so, so the analyst offers only buildable options. When a requirement still asks for more, the coder lists it in `deviations` (artifact `code-gaps`) and the tester lists what its tests cannot check in `gaps` (`test-gaps`). Those requirements never count as verified, even with green tests (`domain/testreport.py: apply_gaps`). Before s03 the coder turned a browser game into a terminal program without a word, and the trace showed the browser requirement as verified.

One agent action per project at a time: a second request while an agent works is refused with 409 (`Orchestrator._claim`), and `GET /projects/{id}` says what is running, so a reloaded page waits instead of sending again.

File artifact ids are slugs of the path (`source-todo-service-py`). Paths that would share an id (`todo/__main__.py` and `todo/main.py`) are refused by the output schema, so the model renames one on its retry instead of one file silently replacing the other. Wings that write files expect the complete set every time; a file left out is retired.

### Choices before an agent starts (ADR 0018)

A generator can offer choices as fields of its input: an `enum` (one of several) or a list of an `enum` (a set of ticks), with a `default` and, optionally, `json_schema_extra={"option_hints": {option: "one line"}}`. The frontend then opens the step on those choices instead of starting the agent on Accept (`choosesFirst` in `lib/flow.ts`, `components/StartChoices.tsx`), and the text box leaves them out. Today:

- Design `generate`: `kinds` (default use case, class, sequence; at least one) and `level` (`simple` default, or `detailed`). The architect gets "Draw exactly these diagram kinds: ...". Every diagram stores `content.level`; `revise` tells the architect to keep the kinds and the level of the current design (`domain/diagrams.py: design_choice`), and the refinement wing tells the reviewer the choice and keeps the level on refined diagrams. A design may lack a sequence diagram (no consistency check then) or a class diagram (no drift check then).
- Tests `generate`: `depth` (`focused` default, or `thorough`). The tester is told "Focused tests: write at most N tests" with N from the acceptance criteria; `limited(N)` refuses more, so the model retries with the count. Without `depth` in the input (Change the tests, a redo) the depth of the last generation is kept (`content.depth` of `test-gaps`).

### Carrying a change through (`refresh_step`)

When a change request moves through the phases (`Orchestrator.advance_change`, `POST /changes/{n}/advance`), the orchestrator asks the wing of the current phase how it brings its own output up to date: `refresh_step(reason, artifacts)` returns the wing's own actions with their input, in the order to run them. `reason` is the change in words (summary, the developer's request, the analyst's instruction); `artifacts` are all of the project's artifacts, so a wing can pick `revise` when it has output and `generate` when it has none. The orchestrator knows no action names and wings still never call each other.

| Wing | Refresh step |
|---|---|
| P1 `requirements` | `revise` with the reason (only used when the change did not start here) |
| P2 `design` | `revise` with the reason as feedback (`generate` with guidance when there are no diagrams) |
| P3 `refinement` | `comment` on the class diagram of the current design with the reason; the comment lists the findings earlier reviews applied, so they survive when the refined copy is rebuilt |
| P4 `codegen` | `revise` with the reason (`generate` when there is no code) |
| P5 `testing` | `generate` with the reason as guidance, then `run` |
| P6 `deployment` | `revise` with the reason (`generate` when there are no files); both run the check and the smoke command at once, so there is no separate check step |
| P7 `maintenance` | none |

`Orchestrator.catch_up` (`POST /projects/{id}/catch-up`, CLI `wings catch-up`, MCP `catch_up`) uses the same `refresh_step` for the first stale phase when no tracked change drives it; `reason` then says what changed upstream. Both share `Orchestrator._update_phase`.

A wing without a refresh step returns `[]` (the default): the change then stops in that phase with a reason and the developer updates it by hand. The first step of a change does not come from here: it is the impact analyst's proposal (`content.first_step` of the change artifact). All steps of one phase run in one `advance` call; then the phase is approved on the developer's behalf if its `approval_problem` is None. The progress and receipt rules are in `domain-model.md`, section "Change tracking".

### Next steps (`data.next_actions`)

A wing can propose what to do next by returning `data={"next_actions": [{"label", "phase", "action", "input"}]}`. The UI shows them as buttons under the agent's newest answer. A step without input runs at once (e.g. "Run tests"); a step with input opens its phase with the input in the composer, so the developer reads it before sending (e.g. the debugger's "Send the fix to Code generation", the impact analyst's "Update the requirements", the consistency check's two repair directions). Wings never call each other: the developer carries the step across, and the orchestrator applies the gates as for any other action.

### Injected bugs (`probe`, P5)

"Do the tests catch bugs?" is answered by code, not by a model. `probe {limit}` ("Inject bugs", default 8, at most 20) is possible only when the latest test run is green and newer than every source and test file (the rule of the approval gate); otherwise 409.

- `domain/mutation.py` (pure, `ast` only) finds every spot it can change and picks `limit` of them, spread over files, operators and functions, with no randomness: the same code gives the same bugs. Operators: `comparison` (`==`/`!=`, `is`/`is not`, `in`/`not in`), `boundary` (`<`/`<=`, `>`/`>=`), `boolean` (`True`/`False`), `logic` (`and`/`or`), `negation` (a `not` removed), `arithmetic` (`+`/`-`, `*`/`/`, `+=`/`-=`), `number` (an integer plus one), `return` (`return x` to `return None`), `call` (a call statement replaced by `pass`). One line changes by source position; the rest of the file stays byte-identical. Never changed: test files, `__init__.py`, strings and docstrings, annotations, decorators, imports, the `__main__` guard, `try ... except ImportError`, enum values, `super()` calls, expressions over several lines.
- The wing runs the same pytest command as `run` once per bug, with that one file replaced. `judge` decides from the exit code and the JUnit XML: `caught` (exit 1 and at least one failed test; the tests and the REQ ids in their names are recorded), `survived` (exit 0, every test passed), `invalid` (pytest stopped before the tests, no report, or the time limit). Invalid runs count for neither side. A run that hits the time limit is `invalid`, not `caught`: no test reported a failure, and a slow machine must not raise the score. The limit per bug is four times the last green run, at least 10 s.
- Artifact `test-strength` (kind `test_strength`, author `system:mutation`): `caught`, `survived`, `invalid`, `total`, `score` (caught / (caught + survived), `null` if nothing could be judged), `mutants` (`id`, `path`, `line`, `column`, `operator`, `description`, `original`, `mutated`, `outcome`, `tests`, `requirements`, `reason`, `seconds`), `by_requirement` (REQ id -> bugs caught by a test named after it), `seconds`, `candidates`, `limit`, `timeout`, `report_revision`. It has no `covers`, so it is never a trace link.
- Freshness: `domain/trace.py: strength_results(artifacts)` gives the counts only while the artifact is newer than every source and test file (same rule as the test report); `TraceView.strength` carries it.
- The reply names the survivors; each of the first three gets a next step that opens `generate` with guidance for a test that would catch it. Message data: `strength` (the counts), `checked_by: "code"`.
- Limits: a surviving bug can be an equivalent change that no test could catch (for example `indent=2` to `indent=3`); the score is a signal, not a proof. Like every action that saves an artifact, `probe` puts an approved testing phase back to draft and marks later phases out of date, so run it before approving.

### Running generated code

`ctx.sandbox` (port `Sandbox`, adapter `adapters/sandbox.py`) runs a set of files in a fresh temporary folder with a timeout and an environment without the developer's secrets. At the time limit, and after a normal end, everything the program started is stopped too (POSIX: the process group; Windows: a job object, with `taskkill /T` as a second line). P5 runs pytest in it, P6 the smoke command. It is a convenience boundary, not a security boundary: generated code runs with the developer's user rights (ADR 0013). Docker is never run by Wings.

## Add or deepen a wing: checklist

1. Read the wing's README in its package; it states what the course requires and a suggested design.
2. For a new wing, start from `PlannedPhase` (registered, gated, no actions); then replace it in `phases/<wing>/__init__.py` with a real module (`module.py`, `schema.py`, `prompts/`), following `phases/requirements/` as the example. Set `implemented` by inheriting from `PhaseModule` instead of `PlannedPhase`.
3. If the wing needs the outside world (run pytest, build Docker), add a **port** in `application/ports.py`, an **adapter** in `adapters/`, a field on `PhaseContext`, and wire it in `bootstrap.py`. Do not call subprocesses or HTTP from the wing itself.
4. New artifact kinds go into `ArtifactKind`; add their trace IDs to `defines`/`covers`.
5. Add a mock script entry for each new agent name in `adapters/mock_scripts/demo_todo.json` so the demo and tests run without API calls.
6. Tests: one test file in `tests/phases/` driving the wing through the orchestrator (see `tests/phases/test_design.py`).
7. Frontend: actions appear automatically, next steps too. A new artifact kind needs a view component in `frontend/src/components/` and a branch in `PhaseWorkspace.tsx` (unknown kinds fall back to their text).
8. Update this page and the wing's README; record the session in `docs/process/`.

## Targeted control

Every action of every wing can be triggered directly, without going through the UI:

```bash
wings run todo-app design revise feedback="Split TaskService into two classes"
wings attach todo-app brief.pdf                     # prints att-001
wings run todo-app requirements revise feedback="Read the brief" --attach att-001
curl -X POST localhost:8810/api/projects/todo-app/phases/design/actions/discuss \
     -H "Content-Type: application/json" -d '{"input": {"question": "Why a repository?"}}'
```

Gates still apply: a phase whose inputs are not approved answers 409.

A change request is carried through the same way:

```bash
wings run todo-app maintenance change request="Tasks need a priority"
wings changes todo-app                # progress per phase, next step, artifacts touched
wings advance todo-app 1              # one phase: run its update, approve it if its checks pass
wings advance todo-app 1 --all        # phase by phase until complete or stopped; --no-approve leaves approval to you
wings catch-up todo-app [--all] [--no-approve]   # bring stale phases up to date, one per call (or all)
```

## Driving Wings from an AI client (MCP)

```bash
pip install -e ".[mcp]"                       # once, in backend/
claude mcp add wings -- <backend>/.venv/Scripts/wings-mcp     # Claude Code (Windows path)
```

Claude Desktop: add to `claude_desktop_config.json`

```json
{ "mcpServers": { "wings": { "command": "C:/.../backend/.venv/Scripts/wings-mcp.exe" } } }
```

Tools: `list_phases`, `list_projects`, `create_project` (optional `folder`), `project_status`, `run_action`, `approve`, `reopen`, `get_artifacts`, `get_trace`, `folder_status`, `set_folder`, `import_folder_changes`, `restore_folder_files`, `list_changes`, `advance_change`, `catch_up`, `check_plantuml`, `check_consistency`. The server uses the same workspace and `.env` as the web app; gates apply; errors come back as `{"error": ...}`.
