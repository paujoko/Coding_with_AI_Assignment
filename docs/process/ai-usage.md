# AI tool usage log

One row per distinct use of an AI tool while building Wings (not the LLMs inside Wings). Interaction modes as in the report questions: **prompting** (chat, copy code), **completion** (inline suggestions in the editor), **agentic** (the tool plans, edits files, runs commands and tests itself).

Effectiveness: ++ worked without correction, + small corrections, o needed real human or test intervention, - failed or had to be redone.

| Date | Who | Tool and model | Mode | Task | Outcome | Effectiveness | Human correction |
|---|---|---|---|---|---|---|---|
| 2026-11-05 | Paul | Claude Code (Opus 5.5) | prompting | Read the 8 lecture PDFs and the project requirements PDF, summarise what the assignment asks | Summary of tasks, deadlines, grading criteria; flagged the passed group deadline | ++ | none |
| 2026-11-05 | Paul | Claude Code (Opus 5.5) | prompting | Brainstorm and sketch a first architecture | Architecture diagram with 8 agents, trace graph and deterministic checks | + | Paul asked to see it as a picture first |
| 2026-11-09 | Paul | Claude Code (Opus 5.5) | agentic | Design, plan, implement, test and document the whole foundation in one session (backend, frontend, docs) | 8 commits, 61 backend and 5 frontend tests passing, P1 and P2 working on the mock | + | none during the run; Paul to review |
| 2026-11-09 | Claude Code for Paul | Claude Code subagent (Opus 5.5) | agentic | Independent code review of the foundation | see `sessions/2026-11-09-s01-foundation.md` | see session log | |
