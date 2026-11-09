# Wings: rules for coding agents

Wings is our course project for "Coding with AI" (HSG, WS 2026): a multi-agent, LLM-based environment that walks a developer through requirements, UML design, refinement, code, tests, deployment and maintenance. Grading focuses on everything except code generation (the "wings").

## Session start

1. Read `docs/code/README.md` (how the code works, where things are).
2. Read the newest file in `docs/process/sessions/` and the end of `docs/process/timeline.md` (what happened last, what is next).
3. Before changing a wing, read its package README (`backend/src/wings/phases/<wing>/README.md`) and `docs/code/wings.md`.

## Which file answers which question

| Question | File |
|---|---|
| How is the code organised, which rules hold? | `docs/code/architecture.md` |
| How do phase states, artifacts and trace IDs work? | `docs/code/domain-model.md` |
| How do I add or extend a wing? | `docs/code/wings.md` |
| How do LLM providers, prompts and the mock work? | `docs/code/llm.md` |
| Which HTTP routes exist? | `docs/code/api.md` (live: `/docs` on the backend) |
| How is the frontend built? | `docs/code/frontend.md` |
| How should the UI look, which tokens and components? | `docs/code/design.md` |
| How do I run and write tests? | `docs/code/testing.md` |
| What happened when, who did it, with which AI tool? | `docs/process/timeline.md`, `docs/process/sessions/` |
| Why was something decided? | `docs/process/decisions/` (ADRs) |
| What went wrong, what are the limits? | `docs/process/lessons.md` |

## Hard rules (enforced where possible)

- **Layers.** `domain` <- `application` <- `phases` / `adapters` <- `bootstrap` <- `api` / `cli` / `main`. Enforced by `backend/tests/architecture/test_layers.py`; never weaken that test to make an import pass.
- **Wings are independent.** A package in `wings/phases/` never imports another wing. Wings exchange data only through artifacts in the store.
- **Deterministic where possible.** Coverage, drift, test results and deployment checks are computed by code; the LLM proposes, code verifies.
- **No paid LLM calls by AI agents.** Coding agents (Claude Code and similar) use the `mock` provider only. Real providers are run by a human who sets `WINGS_LLM_PROVIDER` and the key themselves.
- **Stable trace IDs.** Never renumber existing `REQ-xxx` IDs; new ones continue after the highest ever used.
- **Tests first** for domain, orchestrator and wing behaviour; every bug found gets a test.
- **One visual system.** UI changes use the tokens and components in `docs/code/design.md`; check them in the browser (wide, phone, dark) before committing.

## Commands

```bash
# backend (from backend/)
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/wings --help              # CLI: drive any wing directly
.venv/Scripts/python -m uvicorn wings.main:app --port 8810

# frontend (from frontend/)
npm install
npm run dev                              # http://localhost:5190, proxies /api to 8810
npx vitest run && npx tsc -b --noEmit
```

## Documentation duties (every session)

Two documentation folders, two different jobs:

- `docs/code/` describes the code **as it is now**. When you change behaviour, update the matching page in the same commit. Overwrite, do not append history here.
- `docs/process/` records **how we worked**, append-only, for the presentation and the individual reports. At the end of every session:
  1. add rows to `docs/process/timeline.md` (date, time, who, tool, what, commit),
  2. write `docs/process/sessions/YYYY-MM-DD-sNN-<topic>.md` from `docs/process/sessions/_template.md`,
  3. add a row per AI tool use to `docs/process/ai-usage.md`,
  4. add failures and AI limits you hit to `docs/process/lessons.md`,
  5. record any architecture decision as a new ADR in `docs/process/decisions/`.
- Commit messages: conventional commits, plus a trailer `AI-Assisted: <tool> (<model>), <mode>` when an AI tool wrote or changed the code.

## Style

- English in code and docs. No em-dashes. Plain, short sentences.
- Python: type hints everywhere, Pydantic models for data crossing a boundary, one responsibility per module.
- TypeScript: strict mode, API types in `frontend/src/api/types.ts` mirror the backend DTOs.
