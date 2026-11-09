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
