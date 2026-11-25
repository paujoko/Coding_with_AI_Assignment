# HTTP API

Base `http://localhost:8810/api`. Code: `backend/src/wings/api/`. The OpenAPI page at `/docs` is always current; this page explains intent.

| Method and path | Purpose |
|---|---|
| `GET /settings`, `PUT /settings/llm {provider, api_key?, models?, efforts?}`, `POST /settings/llm/test` | model provider (`mock`, `openai`, `openrouter`, `anthropic`): read (key only as a hint), change (written to `.env`, used at once; `efforts` per tier for Claude), test with one tiny call |
| `GET /settings/diagrams`, `PUT /settings/diagrams {public_server}`, `POST /settings/diagrams/download` | how diagrams become pictures: use plantuml.com, or download plantuml.jar into `tools/` (needs Java) |
| `POST /system/pick-folder {start?, name?}` | opens the operating system's folder dialog (Explorer, Finder) on the computer the backend runs on and waits for the choice: `{path, empty, suggested}`; `path` is `null` when cancelled; `suggested` is a subfolder named after the project when the chosen folder already has files. 422 with a reason when no dialog can be shown (no Tkinter, no display). Only present when the backend has a folder picker (`folder_picker` in `/health`) |
| `GET /system/default-folder?name=<project name>` | where a project with this name gets its files when no folder is named: `{path}` with an absolute path (`<projects dir>/<slug>`, numbered `-2`, `-3`, ... while taken; an empty name gives the slug `project`). `path` is `null` when the backend has no projects directory. Creates nothing; `POST /projects` computes it again |
| `GET /health` | runtime info: `api_version`, `folder_picker` (raise it in `api/app.py` and `frontend/src/api/client.ts` when a response shape the UI relies on changes), provider, models, renderer available, workspace folder |
| `GET /phases` | the wing catalog: id, title, summary, requires, implemented, actions with input JSON schema, agents |
| `GET /projects`, `POST /projects {name, folder?}` | list and create projects; `folder` (absolute path of an empty or new folder) links the project to the developer's own folder at once, 422 with a reason if it cannot be used, and then no project is created. Without `folder` the project gets the default folder (see `/system/default-folder`; the projects directory is created if missing); only a backend without a projects directory creates a project with `folder: null` |
| `GET /projects/{id}` | project with phase statuses, `can_run`, `stale_cause` (the phase whose change made this one stale, else `null`), `running` (`{phase, action, label, started_at}` while an agent works, else `null`) and `folder` (`{path, synced_at}` or `null`), `open_change` (`{number, done, total, next_phase}` for the change being carried through, else `null`) and `stale` (ids of the phases whose status is `stale`, pipeline order, Maintenance never included, e.g. `["codegen", "testing"]`) |
| `DELETE /projects/{id}` | Wings forgets the project: everything it kept in the workspace (artifacts, messages, documents, activity) is moved to `workspaces/.trash/` in one rename and then removed; the id is free again at once. The developer's folder and the files in it are never touched. 204; 404 for an unknown id; 409 while an agent works on the project (no agent can start while the delete runs) |
| `GET /projects/{id}/design-check` | the current class diagram against the current code, computed by code: `{checked: false}` while there is no class diagram or no code, else `{checked, diagram, in_sync, lines}`. The UI uses it to say whether out-of-date code still fits |
| `GET /projects/{id}/folder` | the developer's folder (ADR 0015): `{path, exists, problem, changes}`; each change `{path, change: modified, added or deleted, artifact_id, phase, importable, newer_in_wings, note}`. Recomputed on every call |
| `PUT /projects/{id}/folder {path}` | link a folder (written at once) or unlink with `null` (the files stay); returns the folder status plus `project` |
| `POST /projects/{id}/folder/import {paths?}` | take hand edits over as new revisions by the developer (all importable ones when `paths` is missing); returns `{project, imported, skipped, stale, drift, reply}`. 422 when nothing can be imported |
| `POST /projects/{id}/folder/restore {paths}` | write Wings' version of changed or deleted files back; returns the folder status |
| `POST /projects/{id}/phases/{phase}/actions/{action} {input, attachments?}` | run any action of any wing (targeted control); `attachments` lists uploaded document ids this message refers to (unknown ids: 422). While an agent already works on the project the request is refused with 409 instead of queued |
| `POST /projects/{id}/phases/{phase}/approve` | developer approves |
| `GET /projects/{id}/changes` | change requests, newest first, each with progress per phase, the next step and the receipt of artifacts it touched (see below) |
| `POST /projects/{id}/catch-up {approve?}` | bring the first stale phase up to date, no tracked change needed (see "Catch up" below) |
| `POST /projects/{id}/changes/{n}/advance {approve?}` | carry change `n` one phase further: run the phase's update, then approve it if its checks pass (see below) |
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

## Changes carried through the phases (API version 9, rules tightened in 10)

A change request (`maintenance` action `change`) is tracked by code: the `change-<n>` artifact records every artifact's revision at that moment, and everything below is computed from that baseline (`domain/change.py`). The UI drives it with one call per phase.

`GET /projects/{id}/changes` returns a list, newest first. One element:

```json
{
  "number": 1,
  "artifact_id": "change-1",
  "kind": "change",
  "request": "Tasks need a priority",
  "summary": "Tasks get a priority, and the list shows the most important tasks first.",
  "affected": ["REQ-001", "REQ-002"],
  "state": "open",
  "started_at": "2026-11-23T10:26:30.652505Z",
  "completed_at": null,
  "progress": {
    "phases": [
      {"phase": "requirements", "title": "Requirements", "state": "done", "status": "approved", "updated": true},
      {"phase": "design", "title": "Design", "state": "current", "status": "stale", "updated": false},
      {"phase": "refinement", "title": "Design refinement", "state": "waiting", "status": "stale", "updated": false},
      {"phase": "codegen", "title": "Code generation", "state": "waiting", "status": "stale", "updated": false},
      {"phase": "testing", "title": "Testing", "state": "waiting", "status": "stale", "updated": false},
      {"phase": "deployment", "title": "Deployment", "state": "waiting", "status": "stale", "updated": false}
    ],
    "current": "design",
    "started": true,
    "complete": false,
    "done": 1,
    "total": 6
  },
  "next": {
    "phase": "design",
    "title": "Design",
    "kind": "run",
    "action": "revise",
    "label": "Revise",
    "input": {"feedback": "The requirements changed. ..."},
    "steps": [{"phase": "design", "action": "revise", "input": {"feedback": "The requirements changed. ..."}, "label": "Revise"}],
    "reason": null
  },
  "receipt": [
    {
      "phase": "requirements",
      "title": "Requirements",
      "updated": [{"id": "requirements", "title": "Requirements", "kind": "requirements", "path": "requirements.md", "before": 1, "after": 2, "changed": true}],
      "added": [],
      "removed": []
    },
    {"phase": "design", "title": "Design", "updated": [], "added": [], "removed": []}
  ]
}
```

| Field | Meaning |
|---|---|
| `state` | `open`; `complete` (every phase P1 to P6 approved again after something changed; `completed_at` is set, progress and receipt are frozen); `dropped` (never started and a newer change was requested; `next` is `null`) |
| `progress.phases[].state` | `done`: changed since the change was requested and approved. `current`: the phase to act on. `waiting`: behind the current one. `untouched`: approved and not changed by this change (for a bug: requirements, design, refinement) |
| `progress.phases[].status` | the phase's ordinary status; `updated`: at least one artifact of the phase differs from the baseline |
| `progress.done`, `total` | phases done, and phases this change moves (every state but `untouched`) |
| `next` | `null` when the change is complete or dropped. `kind` `run`: `steps` are the actions `advance` runs in this phase, in order (`action`, `label`, `input` repeat the first; testing has two steps: write tests, run tests). The first step of a change is the analyst's instruction; later phases use the wing's own refresh step. `approve`: the phase is updated and its gate is open. `input`: the agent asked questions, `reason` says so. `blocked`: `reason` says what the developer must do (a failed test run, a failed check) |
| `receipt` | one entry per phase P1 to P6, always all six. `updated`: `before` and `after` are revisions; `changed` is `false` when the new revision has the same text and content as before (a wing wrote a file again without a difference). `added`: `before` is `null`. `removed`: retired by this change |

`POST /projects/{id}/changes/{n}/advance {"approve": true}` (body optional, `approve` defaults to `true`) carries the change one phase further: it runs `next.steps` through the ordinary action path (all gates apply) and then, if `approve` is true, the wing reported a draft and the phase's own gate (`approval_problem`) is open, approves the phase on the developer's behalf. The activity log says so (`phase.approved` with `data.change` and `data.on_behalf`). It never runs more than one phase.

```json
{
  "project": {"id": "todo", "phases": [], "open_change": {"number": 1, "done": 1, "total": 6, "next_phase": "design"}},
  "change": {"number": 1, "state": "open", "progress": {}, "next": {}, "receipt": []},
  "ran": [{"phase": "requirements", "action": "revise", "label": "Update the requirements", "status": "draft", "reply": "5 requirements drafted. ..."}],
  "approved": "requirements",
  "stopped_reason": null
}
```

`project` and `change` have the full shapes shown above. `approved` is the phase approved in this call or `null`. `stopped_reason` is `null` when the next call can go on; otherwise it is a sentence for the developer: open questions, a gate that is closed (for example "Some tests do not pass. ..."), an action that failed (LLM unreachable, unusable output; nothing was saved), approval left to the developer (`approve: false`), or the change is already complete. A loop in the UI: call again while `stopped_reason === null && change.state === "open"`. A stop is an answer with status 200. Status codes: 404 for an unknown project or change number, 409 while another agent action is running on the project.

`open_change` is part of every project view (`GET /projects`, `GET /projects/{id}`, and the `project` inside action, approve, reopen, folder and artifact responses): `{"number": 1, "done": 1, "total": 6, "next_phase": "design"}` for the newest change while it is open, else `null`. `next_phase` is `null` only in the moment before the change is closed.

Change requests made before version 9 have no baseline and are not listed.

`progress.planned` (phase ids) lists the phases the change has to move (the plan of the change request; for older records the first step's phase and what depends on it). A planned phase is `done` only when it got a new revision after the baseline, is approved again and was updated after every phase upstream of it. Approving a stale phase without updating it leaves it `current` or `waiting`, and the change stays `open`; it is never `untouched`. A change closed before this rule (its frozen `closed.progress` has no `planned`) is not trusted: it is shown live (`open` while a planned phase was not updated) and closed again with a fresh receipt when it is complete.

## Catch up (API version 10)

`POST /projects/{id}/catch-up` with body `{"approve": true}` (body optional, default `true`) handles ONE phase per call: the first `stale` phase in pipeline order (Maintenance is never part of it). It runs that wing's `refresh_step` through the ordinary action path (all gates apply). `reason` for the wing is what changed upstream ("Requirements changed, so Design is out of date.", the hand-edited file names if the developer edited the cause phase, and the request of an open tracked change). If an open change plans that phase, the very steps of `advance` run, and after the last phase the change is closed and Maintenance's consistency check runs. With `approve` true and the wing reporting a `draft` whose `approval_problem` is `null`, the phase is approved on the developer's behalf (`phase.approved` event with `data.catch_up` and `data.on_behalf`, plus `data.change` when a change is open). HTTP 200, 409 while another agent action runs.

```json
{
  "project": {"id": "todo", "phases": [], "stale": ["testing", "deployment"], "open_change": null},
  "ran": [{"phase": "codegen", "action": "revise", "label": "Revise", "status": "draft", "reply": "..."}],
  "approved": "codegen",
  "stopped_reason": null,
  "remaining": ["testing", "deployment"],
  "done": false
}
```

`remaining` = phases still stale after the call. `stopped_reason` is a plain sentence when it cannot go on: open questions, a failed check or action, `approve: false` ("... is ready for review. Accept it to continue."), an upstream phase waiting for approval, or a wing without a refresh step ("X cannot be redone by itself. Change it in its step, then accept it."). When nothing is stale: `done: true`, `stopped_reason: "Everything is up to date."`, `ran: []`, `remaining: []`. `done` is also true after the call that updated the last stale phase without stopping. The UI loops while `stopped_reason` is `null` and `done` is `false`.

API version 10: `POST /catch-up`, `stale` in every project view, `progress.planned` in a change. API version 9: `GET /changes`, `POST /changes/{n}/advance`, `open_change` in every project view, `data.change` (the change number) in the answer to `maintenance` `change`. API version 8 (session s04): `folder` in the project, the `/folder` routes, `folder` on `POST /projects`, `GET /design-check`, and `data.speaker` and `data.drift` on messages no agent wrote (the folder sync). API version 7 (session s03): `running` in the project, 409 for a second action, and requirement verdicts `partial` and `not_met` next to the test outcomes in `verified` and the trace's `results` (a declared gap; only `passed` counts as verified). Version 6 (s02, round 7b): every wing implemented, `next_actions`, `results` in the trace.

Error codes: see `architecture.md`, section "Error mapping". Error bodies are `{"detail": ..., "error": "<ExceptionName>"}`.
