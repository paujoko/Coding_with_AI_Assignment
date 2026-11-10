# HTTP API

Base `http://localhost:8810/api`. Code: `backend/src/wings/api/`. The OpenAPI page at `/docs` is always current; this page explains intent.

| Method and path | Purpose |
|---|---|
| `GET /settings`, `PUT /settings/llm {provider, api_key?, models?}`, `POST /settings/llm/test` | model provider: read (key only as a hint), change (written to `.env`, used at once), test with one tiny call |
| `GET /settings/diagrams`, `PUT /settings/diagrams {public_server}`, `POST /settings/diagrams/download` | how diagrams become pictures: use plantuml.com, or download plantuml.jar into `tools/` (needs Java) |
| `GET /health` | runtime info: `api_version` (raise it in `api/app.py` and `frontend/src/api/client.ts` when a response shape the UI relies on changes), provider, models, renderer available, workspace folder |
| `GET /phases` | the wing catalog: id, title, summary, requires, implemented, actions with input JSON schema, agents |
| `GET /projects`, `POST /projects {name}` | list and create projects |
| `GET /projects/{id}` | project with phase statuses, `can_run`, `stale_cause` (the phase whose change made this one stale, else `null`) and `running` (`{phase, action, label, started_at}` while an agent works, else `null`) |
| `POST /projects/{id}/phases/{phase}/actions/{action} {input, attachments?}` | run any action of any wing (targeted control); `attachments` lists uploaded document ids this message refers to (unknown ids: 422). While an agent already works on the project the request is refused with 409 instead of queued |
| `POST /projects/{id}/phases/{phase}/approve` | developer approves |
| `POST /projects/{id}/phases/{phase}/reopen` | approved back to draft |
| `GET /projects/{id}/artifacts?phase=&include_retired=` | latest revisions |
| `GET /projects/{id}/artifacts/{aid}` | one artifact |
| `PUT /projects/{id}/artifacts/{aid} {content?, text?}` | developer edit: new revision, returns stale phases |
| `GET /projects/{id}/artifacts/{aid}/history` | all revisions |
| `GET /projects/{id}/artifacts/{aid}/svg` | rendered PlantUML in the house style, 503 if no renderer or the diagram cannot be drawn |
| `POST /projects/{id}/attachments {name, media_type, content_base64}` | upload a document (text, Markdown, PDF, .docx; 5 MB at most); its text is extracted at once; 422 with a reason if it cannot be read |
| `GET /projects/{id}/attachments` | uploaded documents without their text (`chars` says how much text there is) |
| `GET /projects/{id}/attachments/{aid}` | one document with its extracted `text` |
| `GET /projects/{id}/messages?phase=` | conversation |
| `GET /projects/{id}/events?after=N` | activity log since event N (the UI polls this) |
| `GET /projects/{id}/trace` | trace graph: `covered` (REQ id -> artifact ids), `uncovered`, `unknown_refs`, `ratio`, plus `requirements` (`id`, `title`), `artifacts` (`id`, `title`, `phase`, `kind`, `covers`; P2 diagrams replaced by refined copies are left out) and `results` (REQ id -> outcome of its tests in the latest run) for display |

Action response: `{project, reply, artifacts, data, stale}`. `data` carries wing-specific results (`summary` and `questions` from P1 when it asks, `coverage` from P2 and P3, `drift` from P4, `verified` from P5, `affected` from P7) and `next_actions`: steps the agent proposes, each `{label, phase, action, input}` (see `wings.md`). The agent's message in the conversation carries the same `data`.

API version 7 (session s03): `running` in the project, 409 for a second action, and requirement verdicts `partial` and `not_met` next to the test outcomes in `verified` and the trace's `results` (a declared gap; only `passed` counts as verified). Version 6 (s02, round 7b): every wing implemented, `next_actions`, `results` in the trace.

Error codes: see `architecture.md`, section "Error mapping". Error bodies are `{"detail": ..., "error": "<ExceptionName>"}`.
