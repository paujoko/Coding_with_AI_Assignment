# Session 2026-11-25 s08: delete a project

- **Who:** Paul, Claude Code (Opus 5.5) in the desktop app
- **When:** 2026-11-25
- **Commits:** branch `feature/delete-project`

## Goal

Projects can be deleted from the UI. Done next to another session that works on `main`, without disturbing it.

## Human prompts (verbatim)

> für alles was ich jetzt hier mache schuae dass es die parent session nciht stört, implementiere dass man projecte löschen kann

## What was done

| Time | Step | By | Result |
|---|---|---|---|
| | Own git worktree on `feature/delete-project`; `node_modules` linked, the existing venv with `PYTHONPATH` on the worktree | Claude Code | main checkout and its servers on 8810/5190 untouched |
| | Tests first: delete, id free again, folder kept, unknown id, refused while an agent works, folder held open on Windows | Claude Code | 6 tests red, then green |
| | `FileSystemStore.delete_project`, `Orchestrator.delete_project`, `DELETE /projects/{id}`, API version 11 | Claude Code | whole backend suite green |
| | Bin per row in the project switcher, confirm in place of the row, App switches to another project | Claude Code | 3 frontend tests, typecheck clean |
| | Browser check on the demo model, own backend 8811 with a throwaway workspace, own frontend 5191 | Claude Code | delete of another and of the open project work; folder stays |

## Decisions

- Delete removes only what Wings keeps. The developer's folder and the code in it stay, because it is their code (same line as ADR 0015: Wings never removes files it did not write on request).
- The project folder is first renamed into `workspaces/.trash/`, then removed. One rename makes the delete atomic for readers and frees the id at once, even when Windows keeps a file open and the removal fails.
- Refused (409) while an agent works on the project; while the delete runs, no agent can start.
- Red is used for the confirm of a delete. design.md is updated.

## Problems and how they were found

| Problem | Found by | Fix |
|---|---|---|
| `fetch` wrapper always parsed JSON, a 204 has no body | reading `api/client.ts` before writing the call | 204 returns `undefined` |
| Project switcher on phones is squeezed to 17 px, its menu to 9 px | browser check at 375 px | not caused by this change; open |
| `PhaseWorkspace.test.tsx` "the text box means change this step" fails on main | full vitest run | caused by commit ca6af80 (composer pills removed); open |

## Verification

- Backend: whole pytest suite green, including the layer test.
- Frontend: typecheck clean; 127 of 128 tests green, the one red test fails on main too.
- Browser (demo model): bin on hover, confirm text with the folder, delete of another project, delete of the open project switches to the next one; workspace folder gone, project folder kept, `.trash` empty afterwards.

## Open after this session

- Merge `feature/delete-project` into main.
- Project switcher layout on phones.
- Decide on the composer pills removed in ca6af80 and fix or update the red test.
- CLI and MCP server have no delete yet.
