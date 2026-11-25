# Session 2026-11-25 s12: message bubble and looking around while an agent works

- **Who:** Paul, Claude Code (Opus 5.5) as coordinator, one Claude Code subagent (Opus 5.5)
- **When:** about 16:45 to 17:40 (local time)
- **Commits:** 02e59ec .. 4dcf756 (fast-forward into main), plus this documentation commit

## Goal

After Paul's first demo test run on Claude (hangman): make a sent message visible at once, and let the presenter look at other steps while an agent works.

## Human prompts (verbatim)

> wenn ich eien nachircht abschicke sollte es nicht mehr im prompt stecken bleibein unten sondern sollte als nachricht blase abgeschickt werdne so wie es bei claude auch ist

> kannst dz nacen dass man auch zurück klicken kann und sih das nochmals anschauen kann wärend dem ein coder gerade am coden ist? [...] vorallem für die live demo wäre es sinnvoll wenn wir wärend dem der coder am coden ist nochmals auf design klicken können

> mache mal nur das mit der sprechblase und mit andere Schirtte anscheun der Rest ist egal

## What was done

| Time | Step | By | Result |
|---|---|---|---|
| 15:30 to 16:40 | Collected Paul's wishes during his test run, analysed each in the code, wrote them to a list outside the repo; nothing built until Paul's go | Claude | six items |
| 16:20 | Hangman: checked hand edits from another chat (port fallback), restored the computed RUN.md, added a port test, imported the edits into Wings | Claude | Paul's OK to import |
| 16:50 | One subagent in worktree `../wings-chat` for the two items Paul chose | subagent | 02e59ec, 4dcf756 |
| 17:35 | Coordinator re-ran frontend tests, tsc, backend adapter and architecture tests; fast-forward into main | Claude | |

## Decisions

- The sent message shows at once on the client (`lib/outbox.ts`); the backend keeps saving all or nothing.
- Navigation is open while an agent works; other steps are read-only with a notice; the project switcher and Settings stay locked. This reverses the navigation lock from the s02 review; the ref guard in `App.tsx` keeps late results in their step.
- `WINGS_MOCK_DELAY` (0 to 60 s) for browser checks of waiting screens.
- Not built, on Paul's word: comment in Design review, off-topic questions, skipping tests, coder returning only changed files.

## Problems and how they were found

| Problem | Found by | Fix |
|---|---|---|
| Picked answers lost when sending failed | subagent | restored like the text box |
| Your program's change text lost on failure | subagent | restore added |
| Fonts 403 in a worktree (node_modules junction outside Vite's allowed folders) | browser console | worktree setup only; the main checkout is not affected |
| The tester's redo dropped the hand-added port test in hangman | Claude compared the folder after the redo | none yet; listed with the coder-only-changed-files idea |

## Verification

- Frontend 179 tests in 29 files, tsc clean (coordinator re-ran).
- Backend: adapter and architecture tests green (coordinator); full suite exit 0 with 572 tests (subagent).
- Browser on the mock with a delay, 1440 and 1024 px, light: bubble at once, navigation during a run, notice and Show it, failure with Try again (subagent).
- Not verified: the Redo all loop while looking elsewhere in a browser (unit-tested only); Your program's change box live.

## Open after this session

- A real run with the new screens before the talk.
