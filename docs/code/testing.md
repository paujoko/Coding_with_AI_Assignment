# Testing

## Backend

```bash
cd backend
.venv/Scripts/python -m pytest            # all 170, about 10 s (P5 and P6 tests run pytest for real), no network (macOS/Linux: .venv/bin/python)
.venv/Scripts/python -m pytest tests/architecture
```

| Folder | Covers |
|---|---|
| `tests/architecture` | layer rules, wing independence, stdlib-and-Pydantic-only pure layers (`ast`-based, relative imports resolved) |
| `tests/domain` | phase state machine, staleness, slugs, trace coverage |
| `tests/application` | structured LLM calls and retries, registry validation, orchestrator gates, events, errors, developer edits, concurrent edit during an action, version conflicts, read-only wing context, all-or-nothing saves (with a `FakePhase`) |
| `tests/adapters` | file store revisions and path safety, events, scripted mock, OpenRouter request shape via `httpx.MockTransport`, renderer: no backend, house style insertion, Graphviz error pictures, built-in layout without `dot` |
| `tests/adapters/test_document_extraction.py`, `tests/application/test_attachments.py` | text from text, PDF and .docx files, refusals, attachment storage, size limits, documents reaching the analyst's prompt, unknown ids refused before anything runs |
| `tests/test_settings.py`, `tests/adapters/test_llm_openai.py` | `.env` read and written, provider switch without restart, keys never returned, no-key stand-in, OpenAI request shape and error hints (mock transport) |
| `tests/domain/test_uml.py`, `tests/application/test_tools.py`, `tests/phases/test_design_tools.py` | UML parsers and consistency; the tool loop (results back to the model, unknown tools, invalid arguments, cut-off); the architect using its tools in the demo; a disagreement caught by code |
| `tests/test_mcp_server.py` | the MCP server's tools in-process (skipped if `mcp` is not installed); a real stdio run is described in session s02 |
| `tests/test_openai_end_to_end.py` | the real OpenAI adapter against a fake OpenAI server through P1 and P2, tool round included (answers "is everything ready for a real model?") |
| `tests/test_diagram_settings.py` | plantuml.com on and off, jar download (mock transport) and failure |
| `tests/phases` | every wing through the real orchestrator with the scripted mock; `walk(orch, phase)` (conftest) approves all phases before `phase` on the happy path. P5 and P6 run pytest and the smoke command for real in the `LocalSandbox`: an injected bug fails a test, the debugger points at the code, the fix through code generation makes the tests green; a wrong test is fixed in P5; a Dockerfile copying a missing folder fails the check. P7: impact from the trace, unknown ids dropped, a bug starting in code, a hand edit showing drift with both repair directions |
| `tests/domain/test_code.py`, `tests/domain/test_testreport.py`, `tests/adapters/test_sandbox.py` | design vs code drift; JUnit parsing and requirement links; sandbox runs, timeouts, no secrets in the environment, no paths outside the folder |
| `tests/api` | HTTP happy path P1 to P2, error codes, developer edit making design stale |

Fixtures in `tests/conftest.py`: `demo_script` (the demo mock script as a dict) and `make_orchestrator(script)` (full registry, temporary workspace, scripted LLM).

Rules: every bug gets a test; no test may call a real LLM or the network; prefer driving wings through the orchestrator so gates and events are exercised too.

## Frontend

```bash
cd frontend
npx vitest run
npx tsc -b --noEmit
```

`components/StepList.test.tsx` covers the wing grouping, that only steps waiting for the developer show a word, selection and the hints for locked and stale phases (naming the phase that changed). `components/Composer.test.tsx` covers schema-typed inputs, keeping typed text when an action fails and the required-field check. `components/Conversation.test.tsx` covers question cards (picking, showing the chosen answer, disabled once answered) and inline system steps. `components/DesignView.test.tsx` covers that trace links wait while an agent works. `components/NewProject.test.tsx` covers project names taken from a description. `Conversation.test.tsx` also covers collapsed system steps and that next steps show only under the newest answer. `ReviewView.test.tsx` covers picking and applying findings; `FilesView.test.tsx` covers switching files and editing one into a new revision.

## Manual end-to-end check (mock)

Start backend and frontend, create a project with a description ("Create and start"), answer the three questions by clicking options (they fill the answer box), approve requirements, generate the design, open Traceability (5 of 5 covered). Then reopen requirements and revise them: the design station turns "Out of date" with a broken track, the hint names Requirements as the cause, and the trace still shows 5 of 5 (IDs kept). Check at 1440 and 390 px, light and dark. `frontend/scripts/walkthrough.cjs` does this walk with Playwright and saves screenshots (fresh workspace needed, see the comment at its top). `frontend/scripts/walkthrough-pipeline.cjs` continues from an approved design through P3 to P7 in the UI: apply a finding, generate code, write and run tests through the "Run tests" step, deploy, check consistency, request a change and follow "Update the requirements" into P1.
