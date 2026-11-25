# Session 2026-11-25 s13: every decision in the history

- **Who:** Paul, Claude Code (Opus 5.5) as coordinator, one Claude Code subagent (Opus 5.5)
- **When:** about 17:50 to 19:05 (local time)
- **Commits:** c855f10 .. 601971a (fast-forward into main), plus this documentation commit

## Goal

In the demo the team first walks through a finished product step by step, then changes it live. Everything the developer entered, chose or changed must show in each step's conversation and stay there, and nothing Wings did may look like the developer's words.

## Human prompts (verbatim)

> ich möchte dass du sicherstellst dass alles was man je eingegeben, geändert hat sichtbar ist im verlauf der einzelnen seinten also der urspungsprompt, allfällige änderungen die man als prompt angegeben hat, die fragen die man beantwortet hat, design änderungen etc.

> ok pushe alles auf main

## What was done

| Time | Step | By | Result |
|---|---|---|---|
| 17:55 | Read `run_action`: a developer message only when the action has a message field | Claude | |
| 18:00 | Probe on a mock backend through the API: whole build, then a change carried through every phase; listed messages per phase | Claude | seven gaps, one of them misattribution |
| 18:05 | Subagent in worktree `../wings-history` | subagent | c855f10 backend, 601971a frontend, ADR 0022 |
| 18:25 | Subagent stalled for 10 minutes; resumed with its context | Claude | |
| 18:55 | Coordinator re-ran frontend tests, tsc, history and architecture tests; checked commit identity and that the BOMs in three files predate the branch | Claude | |
| 19:00 | Example project built on the mock for Paul to look at; Paul chose to push at once | Claude | |

## Decisions

- Every developer decision is a message with `data.decision` and a readable line (ADR 0022).
- Wings' actions on the developer's behalf are role `system`, author `wings`, marked `on_behalf`.
- Decision lines are never sent to the agents; on-behalf instructions still are, as before.
- API version 13.

## Verification

- Frontend 189 tests, tsc clean; history (17) and architecture tests green (coordinator).
- Backend full suite 589 passed; browser walk on the mock at 1440 and 1024 px with a change carried by Redo all (subagent).
- Not verified in a browser: the Edit button and a folder import (backend tests only). Not verified with a real model.

## Open after this session

- Build the demo product after this change; older projects keep their gaps.
- Restart the backend after pulling (API 13).
