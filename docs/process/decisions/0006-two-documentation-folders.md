# 0006 Two documentation folders: code and process

- Date: 2026-11-09
- Status: accepted
- Decided by: Paul (instruction), structure by Claude Code (Opus 5.5)

## Decision

- `docs/code/`: describes the code as it is now, for us and for new AI sessions. Overwritten with every change.
- `docs/process/`: append-only record of how we worked (timeline, session logs, ADRs, AI usage, lessons, evidence), for the presentation and the individual reports.
- `CLAUDE.md` at the repository root makes keeping both folders part of every coding session.

## Why

Paul's words: the documentation should make it traceable when what was done, because how we programmed may matter in the presentation. The report (section 9) asks which AI tools were used in which interaction mode and where agents failed; that needs to be recorded while it happens, not reconstructed in December.

## Consequences

Each session costs a few minutes of logging. Git history (commit times, `AI-Assisted` trailers) backs the timeline.
