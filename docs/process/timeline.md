# Timeline

Append-only. Newest at the bottom. Times as recorded on the working machine (see README).

| Date | Time | Who | Tool | What | Commit |
|---|---|---|---|---|---|
| 2026-10-14 | | | | Deadline for group composition (requirements PDF, section 7) | |
| 2026-11-05 | | Paul | Claude Code (Opus 5.5) | Lecture slides and project requirements read; task, deadlines and grading summarised; brainstorming started; first architecture sketch (8 agents, trace graph, deterministic checks) | |
| 2026-11-09 | 11:46 | Paul | | Instruction: lay the foundation, document everything, two doc folders, use brainstorm, plan, implement, test, refactor | |
| 2026-11-09 | 11:46 | Claude Code for Paul | Claude Code (Opus 5.5) | Design document and implementation plan written; repo initialised; layer rules as a test | 0c2f8d4 |
| 2026-11-09 | 11:51 | Claude Code for Paul | Claude Code (Opus 5.5) | Domain: phase state machine, artifacts, activity log, trace coverage (test first) | ce0ec56 |
| 2026-11-09 | 11:53 | Claude Code for Paul | Claude Code (Opus 5.5) | Application: ports, phase contract, LLM agent, registry, structured output with retry | 1245a54 |
| 2026-11-09 | 11:54 | Claude Code for Paul | Claude Code (Opus 5.5) | Adapters: file store, scripted mock, OpenRouter, PlantUML renderer | cbe8539 |
| 2026-11-09 | 11:55 | Claude Code for Paul | Claude Code (Opus 5.5) | Orchestrator: gates, staleness propagation, developer edits, events | 6517f21 |
| 2026-11-09 | 11:58 | Claude Code for Paul | Claude Code (Opus 5.5) | Wings P1 Requirements and P2 Design; P3 to P7 as planned packages; composition root; demo mock script | bd5cc3a |
| 2026-11-09 | 12:00 | Claude Code for Paul | Claude Code (Opus 5.5) | HTTP API and CLI; mock bug found by CLI smoke test and fixed | 40c04ec |
| 2026-11-09 | 12:09 | Claude Code for Paul | Claude Code (Opus 5.5) | Frontend (wingspan, workspace, editors, activity log); 5 UI bugs found in the browser and fixed | c955d83 |
| 2026-11-09 | 12:09 | Claude Code for Paul | Claude Code subagent (Opus 5.5) | Independent review of the whole foundation: 12 findings, 3 high | |
| 2026-11-09 | 12:10 | Claude Code for Paul | Claude Code (Opus 5.5) | Documentation: `CLAUDE.md`, README, `docs/code/`, `docs/process/` with 6 ADRs | 3648acd |
| 2026-11-09 | 12:21 | Claude Code for Paul | Claude Code (Opus 5.5) | Backend review findings fixed (race, path traversal, ID reuse, partial writes, gates, error mapping, architecture test) | 3c539ef |
| 2026-11-09 | 12:23 | Claude Code for Paul | Claude Code (Opus 5.5) | Frontend review findings fixed (navigation while busy, lost input, typed fields) | ca596f2 |
| 2026-11-09 | 12:30 | Claude Code for Paul | Claude Code (Opus 5.5) | Documentation updated to the reviewed state; session log and lessons written | 125a9a6 |
| 2026-11-09 | 12:28 | Paul, Claude Code for Paul | Claude Code (Opus 5.5) | Repository pushed to GitHub (public, on Paul's decision): https://github.com/paujoko/Coding_with_AI_Assignment | fbef00a (pushed head) |
| 2026-11-09 | 11:32 UTC | Paul | | Instruction (cloud session s02): redesign the whole UI so it is uniform, clean, minimal and not "AI slop", with the impeccable skill, a logo, and question everything the first session did | |
| 2026-11-09 | 11:35 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Read docs and code, ran the old UI in a headless browser, screenshots; impeccable skill not installed, its guidance read from its public repository | |
| 2026-11-09 | 11:45 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Backend: diagrams without Graphviz and in the house style, `stale_cause`, trace with titles (tests first) | a57db38 |
| 2026-11-09 | 11:50 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Logo: two rounds of sketches (a fan read as a sunburst, rejected), seven strokes tracing a V chosen | 6dd5501 |
| 2026-11-09 | 11:53 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Frontend rewritten: shell, pipeline line, conversation with system steps, question cards, trace matrix, activity view, first run | 6dd5501 |
| 2026-11-09 | 11:55 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Browser walk found that a revise renumbered all requirements and broke every trace link; fixed with a title fallback (ADR 0008) | 15ec693 |
| 2026-11-09 | 11:58 UTC | Claude Code for Paul | Claude Code subagent (Opus 5.5) | Independent review of the three commits | |
| 2026-11-09 | 12:06 UTC | Claude Code for Paul | Claude Code subagent (Opus 5.5) | Review: 8 findings (1 high: navigation during a running action showed the wrong phase's data) | |
| 2026-11-09 | 12:12 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | All 8 review findings fixed and re-verified with the reviewer's scripts | (this commit) |
| 2026-11-09 | 12:18 UTC | Paul | | Ran the branch locally: crash page without a way back (old backend still running), screen too full; asked to follow ChatGPT / Claude / Claude Code patterns | |
| 2026-11-09 | 12:35 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Old-backend detection and crash recovery; chat-tool layout, less detail by default | (this commit) |
| 2026-11-09 | 12:45 UTC | Paul | | Asked for the three best UI references from a library review, then to rebuild the UI on them with document upload; added prompt-kit as a fourth reference | |
| 2026-11-09 | 13:20 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Document upload end to end (port, adapter, store, orchestrator, API, CLI, UI); chat-kit patterns in the UI | (this commit) |
| 2026-11-09 | 13:30 UTC | Paul | | Steps unclear; wants to only paste an OpenAI key | |
| 2026-11-09 | 14:00 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Numbered steps with action words and a how-it-works panel; OpenAI provider and Settings page writing .env | (this commit) |
| 2026-11-09 | 14:10 UTC | Paul | | Asked for a more radical change: away from the number line, find better references | |
| 2026-11-09 | 14:40 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Steps as a sidebar checklist, project switcher, help as dialog and in empty chats | (this commit) |
| 2026-11-09 | 14:50 UTC | Paul | | Asked whether MCP tools make sense so agents can create UML and more | |
| 2026-11-09 | 15:30 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Tool calling with deterministic UML checks for the architect; Wings as an MCP server (stdio) | (this commit) |
| 2026-11-09 | before 18:50 UTC | Paul | | Pictures do not show locally; continue the whole implementation, take time for design, make the split movable; is everything ready to connect the AI? | |
| 2026-11-09 | 18:50 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Diagram setup in Settings (plantuml.com or jar download), "Set up pictures" in the design view, draggable split, OpenAI end-to-end test against a fake server | c2978c2 |
| 2026-11-09 | 18:55 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | P3 design refinement (findings, apply, comment, refined copy); sandbox port and adapter | d52d416 |
| 2026-11-09 | 19:02 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | P4 code generation, P5 testing (real pytest runs, debugger), P6 deployment (static checks, smoke run) | e0e0d61 |
| 2026-11-09 | 19:06 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | P7 maintenance (change requests with impact from the trace, consistency check); API version 6 | b255ed8 |
| 2026-11-09 | 19:17 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Frontend views for P3 to P7, next-step buttons, traceability with test results; browser walk light, dark, phone | f6436f0 |
| 2026-11-09 | 19:25 UTC | Claude Code for Paul | Claude Code subagent (Opus 5.5) | Independent review of round 7 | |
| 2026-11-09 | 19:35 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | Docs for all wings, ADRs 0012 and 0013, session log | f48a102 |
| 2026-11-09 | 19:30 UTC | Claude Code for Paul | Claude Code subagent (Opus 5.5) | Review of round 7: 10 findings (3 high: stale design after a P2 change, sandbox stdin and secret reads, colliding file ids) | |
| 2026-11-09 | 20:00 UTC | Claude Code for Paul | Claude Code (Opus 5.5), cloud | All 10 review findings fixed with tests; approval gates for P5 and P6; browser check of the drift step | (this commit) |
| 2026-11-09 | about 20:00 UTC | Paul | | Course switched from OpenAI keys to an OpenRouter key per project (DeepSeek V4.1 Flash, daily budget); Paul allowed paid calls for testing | |
| 2026-11-09 | 20:25 UTC | Claude Code for Paul | Claude Code (Opus 5.5), desktop, Paul's Windows machine | Local check: 178 backend and 23 frontend tests, `api_version` 6; key limits read (10 USD per day, workspace budget) | |
| 2026-11-09 | 20:30 UTC | Claude Code for Paul | Claude Code (Opus 5.5), desktop | First real run: design and review returned "placeholder"; raw exchanges showed DeepSeek never calls tools while JSON mode is on | |
| 2026-11-09 | 20:39 UTC | Claude Code for Paul | Claude Code (Opus 5.5), desktop | Fix (JSON mode only without tools) with a test; second real run through all seven wings passed, 0.08 USD; plantuml.jar downloaded through Settings, all diagrams render | (this commit) |
| 2026-11-09 | about 21:10 UTC | Paul | | Commit everything, bring it to `main`, delete the Claude branches | |
| 2026-11-09 | 21:00 to 21:48 UTC | Paul | Wings in the browser, DeepSeek | Own test run "Tik tak toe app": P1 to P5 passed, P6 failed three times; reported the blocked UI, the long wait and the message that stayed in the input box | |
| 2026-11-09 | about 21:50 UTC | Paul | | "verbessere alles": fix everything the run uncovered, restart servers as needed | |
| 2026-11-09 | 21:55 to 23:00 UTC | Claude Code for Paul | Claude Code (Opus 5.5), desktop | 14 fixes with tests (target platform, declared gaps, smoke input, JSON extraction, retries, busy 409 and `running`, composer, tool cache, costs, timeout, design gate, defaults, drift on private names); ADR 0014; API version 7 | (this commit) |
| 2026-11-09 | 22:36 UTC | Claude Code for Paul | Claude Code (Opus 5.5), desktop | Control run on DeepSeek with Paul's scenario: web app, 107 tests green, 11 of 12 verified, smoke check passed, 0.107 USD | |
| 2026-11-14 | 12:58 UTC | Ben | | Instruction: implement an output folder with two-way sync, update the README, stick to the architecture | |
| 2026-11-14 | 13:00 to 13:25 UTC | Claude Code for Ben | Claude Code (Opus 5.5), cloud session on a copy of the repo | Output folder with two-way sync (ADR 0015): domain rules, port and adapter, orchestrator, wing hook for new files, API version 8, CLI, MCP tools, Folder view, banner, start page field; 46 backend and 5 frontend tests; browser check wide, 1024 dark, phone dark | (not committed yet; branch `feature/output-folder-sync` proposed) |
| 2026-11-14 | 13:40 UTC | Ben | Wings on his machine, OpenRouter | First run with the folder: import, drift, design updated from the code; reported the confusing "approve it again if it still fits" | |
| 2026-11-14 | 13:45 UTC | Claude Code for Ben | Claude Code (Opus 5.5), cloud session | `GET /design-check`, "Still fits" card in code generation, resolved drift messages; 2 backend and 1 frontend test | (not committed yet) |
| 2026-11-14 | 13:53 UTC | Ben | Wings on his machine | Reported: Request changes does nothing visible; his messages with code look broken | |
| 2026-11-14 | 14:05 UTC | Claude Code for Ben | Claude Code (Opus 5.5), cloud session, Ben's project copied in | Code shown as code in chat (`RichText`), Request changes with visible state, re-run as default and primary step for out-of-date Testing and Deployment; 4 frontend tests | (not committed yet) |
| 2026-11-14 | 14:09 UTC | Ben | | Asked for the Explorer dialog to choose the folder | |
| 2026-11-14 | 14:20 UTC | Claude Code for Ben | Claude Code (Opus 5.5), cloud session | Folder dialog: `FolderPicker` port, Tkinter adapter in a child process, `POST /system/pick-folder`, Browse button; 6 backend and 2 frontend tests; dialog checked on a virtual display; ADR 0015 amended | (not committed yet) |
| 2026-11-23 | 09:45 UTC | Paul | | Asked for a review of the whole project against the brief, a browser test, and changes on a new branch with full freedom | |
| 2026-11-23 | 10:05 UTC | Claude Code for Paul | Claude Code (Fable 5.2), desktop app, seven subagents | Change propagation with receipt, injected bugs, run guide, folder default, drift with inheritance and attributes, shorter replies, larger type, change tracker, requirement lens, Windows fixes | ea5099e |
| 2026-11-23 | 11:15 UTC | Claude Code for Paul | Claude Code (Fable 5.2), desktop app | Browser check of the new views; overflow fixes; check after a change; process docs, ADR 0016 | b21d4e9 and this commit |
| 2026-11-23 | 14:10 UTC | Paul | | Asked to rethink the whole flow from start to maintenance and to replace the generic look, with full freedom, on a branch | |
| 2026-11-23 | 14:15 UTC | Claude Code for Paul | Claude Code (Opus 5.5), desktop app | Guided flow: one loop (accept or change, redo after a change), result first, Your program, new visual identity; whole build and change checked in the browser on the demo model; ADR 0017 | feature/guided-flow
| 2026-11-23 | 16:30 UTC | Claude Code for Paul | Claude Code (Opus 5.5), desktop app | User walk building chess on the demo model; eight fixes (apply ticked findings, drift lines, last reply, send answers, change tests, slow hint, accept wording, loading line) | feature/walk-fixes |
| 2026-11-25 | | Paul | | Asked to be able to delete projects, worked on a separate branch so a parallel session on main is not disturbed | |
| 2026-11-25 | | Claude Code for Paul | Claude Code (Opus 5.5), desktop app | Delete a project: store, orchestrator, `DELETE /projects/{id}` (API 11), bin and confirm in the project switcher; tests first; checked in the browser on the demo model with its own servers on 8811/5191 | feature/delete-project |
| 2026-11-25 | about 11:15 | Ben | | Asked for failure stack traces with file and line, a fix loop that keeps its context, and a subagent that makes the demo flow shorter and more interactive (diagram choice, leaner tests) | |
| 2026-11-25 | 11:15 to 12:15 | Claude Code for Ben | Claude Code (Opus 5.5), desktop app | Read the LLM log of Ben's expense tracker run; pytest plugin with failure lines, 30 s per test, fix loop memory (`fix-log`), debugger input reordered; ADR 0019 | not committed yet |
| 2026-11-25 | 11:20 to 11:55 | Claude Code subagent for Ben | Claude Code (Opus 5.5), subagent in worktree `../wings-slim` | Diagram kinds and level chosen by the developer, focused/thorough tests with a cap, fewer tool rounds, tests run on click; ADR 0018 | feature/slim-demo (4f83907, 25736fb) |
