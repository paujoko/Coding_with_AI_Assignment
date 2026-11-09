# Process documentation

How we built Wings: who did what, when, with which AI tool, what we decided and what failed. This folder is the raw material for the presentation (about 12 minutes, December 2026) and for each member's individual report (6 pages, section 9 of the project requirements asks exactly these questions).

Everything here is **append-only**. Correct a mistake with a new dated entry, do not rewrite history.

## Structure

| Path | What goes in | Feeds |
|---|---|---|
| `timeline.md` | one row per noteworthy step: date, time, who, tool, what, commit | presentation timeline slide, report |
| `sessions/YYYY-MM-DD-sNN-<topic>.md` | one file per working session, from `sessions/_template.md`: goal, human prompts (verbatim), what the AI did, decisions, problems, verification, numbers | report sections on AI usage and reflection |
| `decisions/NNNN-<title>.md` | architecture decision records (context, decision, alternatives, consequences) | report "design choices and changes of direction" |
| `ai-usage.md` | table of every AI tool use: tool, model, interaction mode (prompting, completion, agentic), task, outcome, human correction needed | report question "which AI tools, which mode, effective for what" |
| `lessons.md` | failures, AI limits, surprises, per phase | report question "where did the agents fail" |
| `specs/` | design documents written before building | |
| `plans/` | implementation plans | |
| `evidence/` | test outputs, screenshots, demo recordings, measurements | slides, backup for the live demo |

## Conventions

- Times are `YYYY-MM-DD HH:MM` in the local time of the machine that did the work, as git records it. Commit times are the ground truth; the timeline refers to commits by short hash. (Paul's machine reported the zone as WEST on 2026-11-09; check it before comparing times across machines.)
- "Who" is `Paul`, `<partner name>`, or the AI tool when it acted on a human's instruction (`Claude Code (Opus 5.5) for Paul`).
- Quote human prompts verbatim (original language) in session logs; they show how we steered the AI.
- Mark AI mistakes as such, with how they were found (test, review, browser check, human).
