# Session 2026-11-23 s07: one loop for building and changing, new look

- **Who:** Paul, Claude Code (Opus 5.5) in the desktop app on Paul's machine, no subagents
- **When:** about 15:15 to 17:30 (local time)
- **Commits:** branch `feature/guided-flow` (from `feature/ux-overhaul`)

## Goal

Rethink the whole user flow from the start page to maintenance instead of patching single screens, and give the interface a look of its own.

## Human prompts (verbatim)

> das ist mir viel zu schnell gegangen ich möchte wirklich dass du dne ganzen ablauf nochmals grundlegend überarbeitest und überlegst wire wir das machen das mit flappy bird war nur ein beispiel, gehe nchmals gründlich drüber

> Enscheide das selbst ich habe keine zeit wie immer ich gebe dir kompletten entscheidungsspielraum, benutzte einfach einen eigenen branch, du kannst es gerne auch ncohmals grundlegend verändern, auch die Farben der UI gefallen mir noch nicht so und sieht zu sehr nach AI slop aus, überlege dir wie man das besser machen kann

## What was done

| Step | By | Result |
|---|---|---|
| Counted what a user has to understand on screen (about ten ideas), checked the brief's control requirement, looked at the running UI | Claude | design doc `docs/superpowers/specs/2026-11-23-guided-flow-design.md` |
| `lib/flow.ts`: step titles, redo order, marks, what Accept does and says, one screen per state, program state; tests first | Claude | 22 tests |
| New step screen, step rail, redo strip, Your program; App wiring for Accept, Redo, Keep, change from Your program | Claude | |
| New tokens, type (Atkinson Hyperlegible Next), rail, highlighter sentence, action bar, phone rail | Claude | |
| Whole build and a whole change on the demo model in the browser (1440, 1024, 390 px, light and dark) | Claude | found and fixed the issues below |
| Removed `next.ts`, `NextCard`, `StepList`, `StatusBadge`, `useCarry`, old status words; docs | Claude | ADR 0017 |

## Problems and how they were found

| Problem | Found by | Fix |
|---|---|---|
| A change from Maintenance left everything "Ready": nothing is stale before the change touches the requirements | browser walk | the redo list also contains the steps an open change has not reached; Wings writes the requirement change at once and opens Requirements |
| Tests were written but not run, so the step offered Accept without a result | browser walk | Tests are run right after they are written; "Run the tests" when they have not run |
| Two solid buttons on one screen (redo strip and step screen, Apply findings) | screenshots | the strip has no solid button; Apply is an outlined button |
| The text box stayed on "Ask a question" after a result arrived | browser walk | the box returns to "Change it" when the state changes |
| "What should change?" heading below the box; a sideways scrollbar of 8 px | screenshots | grid rule scoped; step body clips horizontally |
| Busy line said "working out what the change touches" while bugs were injected | browser walk | the line names what runs |

## Verification

- Frontend: 122 tests, `tsc -b --noEmit` clean. Backend unchanged (no backend file touched).
- Browser, demo model: new project to Your program with one click per step (answers, review finding applied, tests run, bugs injected, deployment), then a change ("priority") from Your program through all six steps: requirements revision 2, code revision 2, 11 tests, example command with `--priority high`, receipt 12 updated. 1440 px light, 1024 px dark, 390 px dark.
- Not verified: a real model run of the new flow (no paid calls); 1024 and 390 px light; keyboard-only use.

## Open after this session

- Paul looks at the branch; merge order: `feature/ux-overhaul`, then `feature/guided-flow` (it builds on it).
- A real DeepSeek run of one build and one change before the presentation.
- `carryChange` and `maintenanceWord` in `lib/changes.ts` are unused by screens.

## Second round (same evening): a user's walk, building chess

Paul: "gehe einmal alles komplett im frontend durch und versetze dich in die Rolle eines Users ... ich möchte dass du ein Schach versuchst zu programmieren". Walked on the demo model (no paid calls), so the content stays the scripted to-do app; the walk judged the handling, not the generated chess.

| Problem a user hits | Fix |
|---|---|
| Design review: F1 is ticked, but the button says "Accept and write the code"; Accept does not apply ticked findings, and the code then differed from the diagram | ticked findings make "Apply N findings" the solid button, "Accept without applying" the link |
| Code: "differs from the class diagram in 1 place", but not where | the lines are listed under the sentence |
| After "Change it" the result looked the same and nothing said what the agent did | the agent's reply to the latest request stands above the result |
| Answering questions: only a small round arrow sends | "Send 2 of 3 answers" as the solid button |
| Tests could not be changed by typing | "Change the tests" as a named second choice; questions stay the default |
| A real step takes minutes with only a timer | a hint after 15 seconds |
| The agent and backend texts said "approve" | "accept" in replies and stop reasons |
| A blank screen while the app loads | "Opening Wings" |

Not fixed: the project name is the first words of the description ("Schach fuer zwei Spieler"); the drift fix only goes one way (code to diagram), so when the code is right the developer has to accept anyway or change the design by hand.

Verification: frontend 125 tests, backend suite green (three assertions updated to the new texts), each fix seen in the browser at 1440 px.