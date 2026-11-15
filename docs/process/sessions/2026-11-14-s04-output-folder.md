# Session 2026-11-14 s04: output folder with two-way sync

- **Who:** Ben, Claude Code (Opus 5.5) in a cloud session working on a copy of the repository from Ben's machine
- **When:** 13:58 to about 14:25 (local time)
- **Commits:** none yet; the change is handed over uncommitted, a branch `feature/output-folder-sync` is proposed

## Goal

Let the developer choose a folder on their computer for a project's files, and keep that folder and Wings in sync both ways, so a hand edit in the developer's own editor is detected, checked against the design and taken over on request (criteria C2, C3).

## Human prompts (verbatim)

> okay, implement output folder with two-way sync. make sure to update the readme & stick to the architecture

> ja das uml stimmt, dann ist aber diese warnung verwirrend

> the request changes button does not work. also I cannot see my promts in the chat, they are not displayed nicely

> kannst du implementieren, dass wenn ich den folder auswähle der explorer aufgeht und ich so den ordner auswählen kann

Earlier in the same conversation Ben asked whether the user can choose where the code is written ("gibt es die möglichkeit, dass der user im ersten schritt angibt wo auf dem computer der code hingeschrieben werden soll?") and what a two-way sync does.

## What was done

| Time | Step | By | Result |
|---|---|---|---|
| 14:00 | Read store, orchestrator, ports, wings, API, CLI, MCP, frontend | Claude | Plan: folder as a second copy, rules in the domain, one port and adapter, manifest in the project |
| 14:03 | `domain/folder.py`, `domain/sync.py` with 16 tests first | Claude | layout, fingerprints, export plan, change detection |
| 14:05 | `ProjectFolder` port, `LocalProjectFolder` adapter, 13 tests | Claude | path checks, ignored folders, binary files, nothing written outside the folder |
| 14:07 | Wing hook `adopt_developer_file` (codegen, testing); orchestrator `set_folder`, `folder_status`, `import_folder_changes`, `restore_folder_files`, sync after every change; 13 orchestrator tests on the demo script | Claude | all green first run |
| 14:10 | API (version 8), CLI `wings folder`, MCP tools; API and MCP tests | Claude | the API test found a 500 for import without a folder; fixed to 422 |
| 14:12 | Frontend: types, client, `FolderView`, sidebar entry with count, banner, start page field, 5 tests | Claude | `tsc` clean, 30 tests |
| 14:15 | Browser walk with Playwright: start page with folder, demo pipeline, edit `models.py` and `DEPLOY.md` by hand, banner, Folder view, import, code generation chat; phone dark and 1024 dark | Claude | two display problems found in screenshots and fixed (restore button row, speaker of the import message) |
| 14:20 | ADR 0015, docs/code (architecture, domain model, API, frontend, wings, design, README), README, process logs | Claude | |

| 14:40 | Ben ran it on his machine (OpenRouter): import, drift shown, "Update the design from the code", refinement approved. Code generation then said "approve it again if it still fits", and the old drift message still offered its buttons | Ben | confusing |
| 14:45 | `GET /design-check` (orchestrator `design_check`), "Still fits" card in code generation, "Resolved since" on the old message; tests and a browser check of exactly Ben's sequence | Claude | the card now says what code knows |

| 14:53 | Ben: "the request changes button does not work. also I cannot see my promts in the chat, they are not displayed nicely" | Ben | |
| 14:55 | Ben's project copied and opened locally: code in messages flattened and overflowing; Request changes without visible effect; his "run the tests" had gone to Write tests twice | Claude | three causes |
| 15:05 | `RichText` for chat messages, Request changes with visible state, default action and a re-run button for out-of-date phases; 4 frontend tests; browser check on Ben's project | Claude | |

| 15:09 | Ben: "kannst du implementieren, dass wenn ich den folder auswähle der explorer aufgeht und ich so den ordner auswählen kann" | Ben | |
| 15:12 | `FolderPicker` port, `NativeFolderPicker` adapter (Tkinter in a child process), `POST /system/pick-folder` with a suggested subfolder for a folder that has files, `FolderField` with Browse on the start page and in the Folder view; 6 backend and 2 frontend tests; the dialog opened for real on a virtual display from a click in the browser | Claude | |

## Decisions

- The developer's folder is a second copy, not the store; the manifest lives in `project.json` (ADR 0015).
- Wings writes after every change but never over a hand edit; imports and restores happen only on the developer's request.
- Layout: program at the top, Wings' documents in `docs/wings/`.
- Content checks stay in the wings (`apply_developer_edit`, new `adopt_developer_file`); the orchestrator never parses code itself.
- Messages no agent wrote carry `data.speaker`, shown in the chat instead of the agent's name.

## Problems and how they were found

| Problem | Found by | Fix |
|---|---|---|
| `import` on a project without a folder answered 500 (assert) | API error-case test | checked first, 422 with "set one first" |
| Restore button on its own centred row | screenshot 1440 px | fixed grid position |
| Import result in the code generation chat labelled "Coder" | screenshot after import | `data.speaker` |

## Verification

- Backend: 253 tests pass (199 before; 54 new), layer test unchanged and green.
- Frontend: 37 tests pass (12 new), `tsc -b --noEmit` clean.
- CLI by hand: `wings create --folder`, `wings folder`, `--restore`, `--import` with nothing to import.
- Browser (demo model, no console errors): 1440 light, 1024 dark, 390 dark. A hand-added `archive()` method was reported as "Task.archive() is in the code but not in the class diagram" with both repair buttons; a deleted `cli.py` as "Cli is in the class diagram but not in the code".
- Ben ran it on Windows with OpenRouter: link, write, hand edit, import, drift, design update from the code all worked; the hint afterwards was confusing and was fixed (see above).
- Not tested before Ben's run: Windows paths on a real Windows machine (the tests run on Linux; the adapter uses `pathlib` only), a real model run.

## Numbers

- New files: `domain/folder.py`, `domain/sync.py`, `adapters/project_folder.py`, `components/FolderView.tsx`, four test files, ADR 0015.
- About 900 lines of code and tests added.

## Open after this session

- Ben: run it on Windows with a real folder (`C:\...`), then commit on a branch and let Paul review.
- Drift check: attributes and associations are still not compared (now more visible, because hand edits often add attributes).
- Optional: a "Check consistency" button in the Folder view once P7 is unlocked; today the result of the import already shows the drift.
