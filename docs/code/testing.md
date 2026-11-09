# Testing

## Backend

```bash
cd backend
.venv/Scripts/python -m pytest            # all, about 8 s, no network
.venv/Scripts/python -m pytest tests/architecture
```

| Folder | Covers |
|---|---|
| `tests/architecture` | layer rules and wing independence (`ast`-based) |
| `tests/domain` | phase state machine, staleness, slugs, trace coverage |
| `tests/application` | structured LLM calls and retries, registry validation, orchestrator gates, events, errors, developer edits (with a `FakePhase`) |
| `tests/adapters` | file store revisions and path safety, events, scripted mock, OpenRouter request shape via `httpx.MockTransport`, renderer fallback |
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

`components/Wingspan.test.tsx` covers the wing grouping, status labels, selection and the hints for locked and stale phases.

## Manual end-to-end check (mock)

Start `wings-backend` and `wings-frontend`, create a project, Start with any description, answer the three questions (chips fill the answer box), approve requirements, generate the design, then edit a requirement: design must show "Out of date" and the activity log must contain `phase.stale`.
