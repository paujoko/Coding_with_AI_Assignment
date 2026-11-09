# Testing

## Backend

```bash
cd backend
.venv/Scripts/python -m pytest            # all 89, about 10 s, no network (macOS/Linux: .venv/bin/python)
.venv/Scripts/python -m pytest tests/architecture
```

| Folder | Covers |
|---|---|
| `tests/architecture` | layer rules, wing independence, stdlib-and-Pydantic-only pure layers (`ast`-based, relative imports resolved) |
| `tests/domain` | phase state machine, staleness, slugs, trace coverage |
| `tests/application` | structured LLM calls and retries, registry validation, orchestrator gates, events, errors, developer edits, concurrent edit during an action, version conflicts, read-only wing context, all-or-nothing saves (with a `FakePhase`) |
| `tests/adapters` | file store revisions and path safety, events, scripted mock, OpenRouter request shape via `httpx.MockTransport`, renderer: no backend, house style insertion, Graphviz error pictures, built-in layout without `dot` |
| `tests/phases` | requirements and design wings through the real orchestrator with the scripted mock |
| `tests/api` | HTTP happy path P1 to P2, error codes, developer edit making design stale |

Fixtures in `tests/conftest.py`: `demo_script` (the demo mock script as a dict) and `make_orchestrator(script)` (full registry, temporary workspace, scripted LLM).

Rules: every bug gets a test; no test may call a real LLM or the network; prefer driving wings through the orchestrator so gates and events are exercised too.

## Frontend

```bash
cd frontend
npx vitest run
npx tsc -b --noEmit
```

`components/Pipeline.test.tsx` covers the wing grouping, status labels, selection, the broken track into a stale phase and the hints for locked and stale phases (naming the phase that changed). `components/Composer.test.tsx` covers schema-typed inputs, keeping typed text when an action fails and the required-field check. `components/Conversation.test.tsx` covers question cards (picking, showing the chosen answer, disabled once answered) and inline system steps. `components/DesignView.test.tsx` covers that trace links wait while an agent works. `components/NewProject.test.tsx` covers project names taken from a description. `Conversation.test.tsx` also covers collapsed system steps.

## Manual end-to-end check (mock)

Start backend and frontend, create a project with a description ("Create and start"), answer the three questions by clicking options (they fill the answer box), approve requirements, generate the design, open Traceability (5 of 5 covered). Then reopen requirements and revise them: the design station turns "Out of date" with a broken track, the hint names Requirements as the cause, and the trace still shows 5 of 5 (IDs kept). Check at 1440 and 390 px, light and dark. `frontend/scripts/walkthrough.cjs` does this walk with Playwright and saves screenshots (fresh workspace needed, see the comment at its top).
