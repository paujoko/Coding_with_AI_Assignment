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
