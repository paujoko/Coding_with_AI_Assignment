# Architecture

Ports and adapters (hexagonal architecture) with a plugin registry of phases. Decision and alternatives: `docs/process/decisions/0001-ports-and-adapters-with-phase-plugins.md`.

## Layers and what each may import

```plantuml
@startuml
skinparam componentStyle rectangle
package "wings.domain" as D
package "wings.application" as A
package "wings.phases.<wing>" as P
package "wings.adapters" as AD
package "wings.bootstrap" as B
package "wings.api / cli / main" as UI
A --> D
P --> A
P --> D
AD --> A
AD --> D
B --> P
B --> AD
B --> A
UI --> B
UI --> A
@enduml
```

| Layer | Holds | May import | Must not import |
|---|---|---|---|
| `domain` | Project state machine, phases, artifacts, activity, trace coverage | stdlib, Pydantic | every other layer, web or HTTP libraries |
| `application` | Ports, phase contract, `LLMAgent`, registry, orchestrator, structured LLM calls | `domain` | phases, adapters, api, bootstrap, config |
| `phases/<wing>` | One wing: module, schemas, prompts | `domain`, `application` | other wings, adapters, api, bootstrap, config |
| `adapters` | Store, LLM providers, renderer, document text extraction, sandbox for generated code, the developer's project folder, the operating system's folder dialog | `domain`, `application` (ports) | phases, api, bootstrap |
| `bootstrap` | Composition root | everything | (nothing imports it except api entry points) |
| `api`, `cli`, `main`, `mcp_server` | HTTP, command line, MCP server for AI clients | `application`, `domain`; `main`, `cli` and `mcp_server` also `bootstrap` | adapters, phases (api only) |

`backend/tests/architecture/test_layers.py` parses every module with `ast`, resolves relative imports to absolute names, and fails with `file:line imports X` if a rule is broken. It also checks that wings do not import each other, and that `domain`, `application` and `phases` import nothing but the standard library and Pydantic (and none of `subprocess`, `socket`, `urllib`, `http`): a wing that needs the outside world gets a port.

## Why this shape

- **Wings are plugins.** Each phase is a package exposing `MODULE`; `bootstrap.PHASES` lists them in pipeline order. A teammate can build P5 Testing without touching P1 to P4.
- **The orchestrator is the deterministic manager.** Gates, approvals, staleness and the activity log never depend on an LLM.
- **Ports keep the core testable.** All backend tests run on the scripted mock and a temporary folder, with no network; P5 and P6 tests run generated code through the real `LocalSandbox`.
- **Agents use tools, code runs them.** An agent may call deterministic, read-only tools (`application/tools.py`: PlantUML syntax, class/sequence consistency, requirement coverage) before it answers; the agent loop runs them and logs every call as `agent.tool_call`. Tools never write: results still go through the orchestrator.
- **Wings is an MCP server.** `mcp_server.py` offers the targeted-control operations and the UML checks to AI clients over MCP (stdio). It is an entry point like the CLI and follows the same gates.

## Request flow: running a phase action

```plantuml
@startuml
actor Developer
participant "Frontend / CLI" as UI
participant "api.app" as API
participant Orchestrator
participant "PhaseModule (wing)" as W
participant LLMAgent
participant "LLMClient port" as LLM
participant "ArtifactStore port" as S
Developer -> UI : action + input
UI -> API : POST /projects/{id}/phases/{phase}/actions/{action}
API -> Orchestrator : run_action()
Orchestrator -> S : load project
Orchestrator -> Orchestrator : gate: inputs approved? input valid?
Orchestrator -> S : append developer message, event action.started
Orchestrator -> W : run(action, input, ctx)
W -> LLMAgent : ask(turns, schema)
LLMAgent -> LLM : complete() (up to two retries on invalid JSON)
LLM --> LLMAgent : reply
LLMAgent -> S : event agent.llm_call (model, time, cost)
W --> Orchestrator : ActionOutcome(status, reply, artifacts, data)
Orchestrator -> S : save artifact revisions
Orchestrator -> Orchestrator : project.mark_changed() -> stale dependants
Orchestrator -> S : save project, agent message, events
Orchestrator --> API : ActionResult
API --> UI : JSON
@enduml
```

If the LLM fails (provider error or invalid output after the retry), nothing is saved, a `phase.error` event is logged and the API answers 502.

## Consistency guarantees (orchestrator and store)

| Guarantee | How |
|---|---|
| One request per project at a time | a lock per project held for load, run, save; an edit made while an agent works waits and is applied after it |
| No silent overwrite by another process (CLI next to the server) | `Project.version`; the store refuses to save a copy loaded at an older version (`ConflictError`, 409) |
| All or nothing | every returned artifact is checked (`store.check_artifact`) before the first is written; the developer's message is only stored when the action succeeded; files are written atomically (temp file and rename) |
| A read never meets a half-done save | `project.json` is the one file rewritten in place: the store reads it under the same lock it saves under. For another process (CLI next to the server) and for Windows, where a read or a rename fails with `PermissionError` while the other side has the file open, reads and renames are tried again for up to one second (`fs_store._retrying`) |
| Wings cannot bypass the rules | a wing gets a deep copy of the project and a `ReadOnlyStore`; it may only report `draft` or `needs_input`; approval belongs to the developer |
| Files stay inside the workspace | artifact ids are lowercase slugs; paths must be relative POSIX paths, no `..`, backslashes or drive letters, and must resolve under `<project>/files` |
| The log never stops at "started" | any failure inside a wing writes a `phase.error` event |
| Hand edits in the developer's folder are never lost | Wings writes to the folder after every change but skips any file whose text differs from what it last wrote there (manifest with SHA-256 per file in `Project.folder`); taking an edit over (import) or dropping it (restore) is the developer's choice; imports are built and checked for all files before the first is saved; a folder problem is logged (`folder.error`) and never fails the action (ADR 0015) |

## Output folder: the second copy of the files (ADR 0015)

```
artifacts (store)  --plan_export-->  developer's folder        after every action, edit and import
                   <--import-------  (hand edits)              only when the developer chooses
```

Every project has a folder when the installation has a projects directory (`Settings.projects_dir`: `WINGS_PROJECTS_DIR`, else `~/WingsProjects`; `bootstrap` hands it to `LocalProjectFolder`). A project created without a named folder gets `<projects dir>/<project slug>`, or `<slug>-2`, `-3`, ... while that folder has something in it or belongs to another project (`Orchestrator.default_folder`, chosen and linked inside the create lock). The projects directory is the only parent Wings creates itself, and only when a project is linked there. An orchestrator built without a projects directory (most tests) keeps the old behaviour: no folder unless one is named, so tests never write into the real home folder.

Two rules of the adapter the orchestrator relies on: `same(a, b)` compares folders resolved and, on Windows, without case, so `C:\x` and `c:\x\` are one folder and setting the linked folder again in another spelling keeps the link and its manifest; `is_empty(path)` is true only for a missing folder or one that holds nothing but a fresh `.git` (and files such as `desktop.ini`), so a folder with only pictures, files over 1 MB or dot-folders is not taken for a free one (`read_files` skips all of those and is not used for this question).

Choosing the folder: a browser never tells a page the full path of a folder, so the backend (which runs on the developer's computer) opens the operating system's dialog through the `FolderPicker` port; `adapters/folder_picker.py` runs Tkinter's `askdirectory` in a short child process (Tk wants its own main thread; a child can be stopped when nobody answers). Not an orchestrator concern: it is wired into the API like the settings services.

The rules are pure functions in `domain/sync.py` (layout, fingerprints, what to write, what counts as a change). The orchestrator runs them; `adapters/project_folder.py` is the only code that reads or writes the developer's disk and refuses anything outside the chosen folder. Content checks belong to the wings: `apply_developer_edit` for a changed file, `adopt_developer_file` for a new one (codegen takes program files, testing takes `tests/`). After an import the orchestrator compares the current class diagram with the code (`domain/code.py`) and posts the result, with the two repair directions as next steps, into the changed phase's conversation.

## Error mapping

| Exception | Meaning | HTTP |
|---|---|---|
| `NotFoundError` | unknown project, phase, action or artifact | 404 |
| `PhaseLockedError` | upstream phases not approved | 409 |
| `InvalidTransitionError` | e.g. approve without output, planned wing, wing reporting a forbidden status | 409 |
| `ConflictError` | project saved by someone else meanwhile, or an agent already works on the project | 409 |
| `InvalidInputError`, Pydantic `ValidationError` | input the developer can fix (bad action input, invalid hand edit) | 422 |
| `ActionFailedError` | LLM unreachable, unusable output, or an internal error inside a wing | 502 |
| anything else | a bug | 500 |
