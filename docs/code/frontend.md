# Frontend

React 18, TypeScript (strict), Vite 6, Vitest 3. Code: `frontend/src/`. Visual system and rules: `design.md`.

## Structure

| File | Job |
|---|---|
| `App.tsx` | state: health, wing catalog, projects, selected project, view (`phase`, `trace`, `activity`, chosen in the sidebar), phase, focus, messages, artifacts, trace, events; polling of the activity log (0.6 s while busy, 3 s otherwise); create-and-start; navigation between requirements and diagrams |
| `api/client.ts`, `api/types.ts` | typed fetch wrapper; types mirror backend DTOs; errors become readable `ApiError` messages |
| `components/Sidebar.tsx` | brand, project switcher, step checklist, project views (Traceability, Activity, How it works), model line that opens Settings; on phones a top bar with chip rows |
| `components/ProjectSwitcher.tsx` | current project with its progress mark, menu with all projects and "New project" |
| `components/StepList.tsx` | the seven phases as a grouped checklist with status icons; a word only where the developer has to act |
| `components/NewProject.tsx` | start page like a new chat: one input, examples, Enter creates the project (name from the description, `nameFrom`) and runs P1 `start` |
| `components/PhaseWorkspace.tsx` | title and badge, chat with the dock (next-step card and input), results panel once there are results, Chat / Results switch on narrow screens; holds the composer values so question cards can fill them |
| `components/Conversation.tsx` | messages and the phase's system events in time order, quiet steps collapsed per turn; question cards with clickable answers; files a message was sent with; copy button on agent replies; a live checklist while the agent works; a button back to the newest message; a one-click start in an empty chat |
| `components/Composer.tsx` | chat input box: attached files as chips, fields generated from the action's input JSON schema, attach button, action pills, round send button; paste files into the text box; `Ctrl+Enter` submits |
| `components/DropZone.tsx`, `components/FileChips.tsx`, `lib/attachments.ts` | drag files anywhere onto the page; chips for waiting and sent files; `usePendingFiles` uploads at once and hands the ids to the next message |
| `components/RequirementsView.tsx` | requirements with acceptance criteria and links to the diagrams that cover them; structured editor (title, description, criteria, type, priority); saving creates a developer revision |
| `components/DesignView.tsx` | coverage summary (links to the trace), one tab per diagram, picture or editable PlantUML source, covered requirement IDs link back |
| `components/SettingsView.tsx` | Settings page. Diagrams: use plantuml.com or download PlantUML; status of the renderer. AI model: provider choice, paste a key (stored in `.env` by the backend), models per tier, test connection; opened from the model line at the bottom of the sidebar |
| `components/Splitter.tsx` | the draggable line between chat and results (mouse, touch, arrow keys, Home or double-click to reset); width kept in localStorage |
| `components/HowItWorks.tsx` | `Loop` (talk, check, approve; also in empty conversations) and the How it works dialog with the legend |
| `components/ReviewView.tsx` | P3 findings as rows with severity and a checkbox (open findings above low are picked); "Apply N findings" runs `apply` |
| `components/FilesView.tsx` | P4 to P6 files: a list like the files of a pull request, the open file as a numbered listing with copy, download, and edit into a new revision; "Download all" |
| `components/TestReportView.tsx`, `components/DeploymentCheckView.tsx` | computed results as a one-line verdict and a check list (failures first); console output folded |
| `components/MaintenanceViews.tsx` | P7 `ChangesView` (each change: kind, request, affected requirements with what traces to them, plan) and `ConsistencyView` (drift lines, per requirement: design, code, tests, result) |
| `components/Covers.tsx` | the requirement chips of an artifact ("Covers", "Implements") |
| `components/TraceView.tsx` | requirement x artifact matrix from `GET /trace`: diagrams, code and tests grouped by phase (files that trace to nothing are left out), the latest test result per requirement next to its name |
| `components/ActivityView.tsx` | the whole project log, newest first (replaces the old `ActivityLog.tsx`) |
| `components/Mark.tsx`, `lib/mark.ts` | the logo; with `phases` each stroke shows a phase status |
| `components/Icon.tsx`, `components/StatusBadge.tsx` | icon set and status badge |
| `components/ErrorBoundary.tsx` | render errors show a card with a way back; wraps the main area (reset on every project, view or phase change) and, as a last resort, the whole app |
| `lib/status.ts` | status labels, "what to do next" hints (derived from the backend's rules, including `stale_cause`), wing grouping, event labels |
| `lib/format.ts` | author and agent names (`agent:impact_analyst` -> Impact analyst, `system:pytest` -> pytest), clock, downloads |

## Behaviour worth knowing

- New actions in a wing need no frontend change: the composer renders a field per input property by its schema type (text, number, checkbox, select for enums, one-per-line list for arrays). The `answer` tab is only shown while a phase waits for answers.
- New artifact kinds need a view component and a branch in `PhaseWorkspace.tsx`; unknown kinds fall back to showing their text. Order in the results panel: verdicts first (consistency, changes, review, test results, deployment check), then diagrams, then files.
- Next steps: `data.next_actions` of the newest agent message become buttons under it. A step for this phase without input runs at once; any other step opens its phase with the input in the composer and that action selected (`App.tsx` keeps it as `prefill` until the action ran), so the developer reads the proposal before sending it.
- Trace navigation: a requirement's "In ..." links open the diagram in its phase; a diagram's covered IDs and the matrix rows open the requirement and highlight it.
- While an agent works, every way to another phase is disabled (pipeline, view switch, project list, trace links, requirement chips), so a result always lands in the phase and project that asked for it. As a second guard, `App.tsx` keeps what the screen shows in a ref and drops any response that arrives for another project or phase (slow loads, quick clicks).
- If "Create and start" fails at the start step, the project exists and the description waits in its start composer.
- Selection groups (view switch, diagram tabs, composer actions) are buttons with `aria-pressed`, not ARIA tabs.
- Nothing typed is lost on failure: the composer clears only after the backend accepted the action, editors keep their draft when a save fails.
- `GET /health` reports `api_version`; when it differs from `API_VERSION` in `api/client.ts` the app shows "The backend runs older code than this interface". `api.trace` fills missing fields with defaults, so an older backend cannot crash a view.
- Documents: uploaded as soon as they are added (like a chat app), sent as ids with the next message. On the start page files wait until the project exists, then go up before P1 starts. The results panel lists every document of the project.
- Downloads: requirements as `requirements.md`, each diagram as its `.puml` source, each generated file under its name, all files of a phase as one text file.
- Fonts are bundled (`@fontsource/host-grotesk`, `@fontsource/jetbrains-mono`); the app makes no request outside its own backend.

## Run

```bash
npm install
npm run dev          # 5190, proxies /api to 8810
npx vitest run       # component and logic tests
npx tsc -b --noEmit  # typecheck
npm run build
```
