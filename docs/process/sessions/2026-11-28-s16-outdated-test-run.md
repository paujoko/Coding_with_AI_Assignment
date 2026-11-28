# Session 2026-11-28 s16: change video on the showcase, outdated test run

- **Who:** Paul, Claude Code (Opus 5.5) driving Wings (Claude Sonnet 5.5) in the browser
- **When:** 11:00 to 11:50 (local time)
- **Commits:** this commit

## Goal

Record the three demo changes again on a copy of the "Split the bill" showcase, so the video ends in the same program the live demo shows. Paid runs approved by Paul up to 6 USD.

## Human prompts (verbatim)

> Es muss aber die richtige UI sein und einfach den Change nochmal highlighten und auch im Video den Change highlighten, welchen man dann in der UI sieht.

> Ja, bis 6 USD

## What was done

| Time | Step | By | Result |
|---|---|---|---|
| 11:01 | Copy of Split the bill as "Split the bill (changes)" with its own folder | Claude Code | the original stays as shown live |
| 11:03 to 11:21 | Three changes recorded in the UI: total spent (requirement), `BalanceCalculator` (design), a hand-written method and "Update the design from the code" | Wings, Sonnet 5.5 | changes 1 and 2 carried; change 3 stopped at Tests, 1 of 20 failing |
| 11:22 | Failing test read against the requirements | Claude Code | the test was wrong: REQ-007 gives the leftover cent to the earliest member, so +8.33, not +8.34 |
| 11:23 to 11:29 | "Change the tests" with that reason | Wings tester | test fixed, 19 tests pass when run by hand |
| 11:30 | The Tests step still showed "1 of 20 tests fail" and no "Run the tests" | Claude Code | frontend bug, fixed with two tests |
| 11:33 | Tests run, accepted, deployment carried | Wings | all six steps accepted |

## Decisions

- A test report counts in the UI only while it is newer than every live test and source file, the same rule as the backend's `fresh_report`. No ADR: it aligns the UI with an existing backend rule.

## Problems and how they were found

| Problem | Found by | Fix |
|---|---|---|
| After "Change the tests" the step kept the old failures as its result and offered only "Explain the failures" and "Accept anyway"; the backend refused to approve because the run was outdated, so the step was stuck | the recording script looped on the Tests step; screenshot | `PhaseWorkspace.tsx` checks the report's age; `flow.ts` says "The tests have not run on the current code and tests yet." |
| A regenerated test contradicted REQ-007 (extra cent) | reading the assertion against the requirement | developer guidance through "Change the tests" |

## Verification

- Frontend: 192 tests pass (two new), `tsc -b --noEmit` clean.
- In the real UI: after the fix the Tests step offered "Run the tests"; the run was green and the change carried to the end.

## Numbers

- 4.41 USD for the three changes and the test fix (Sonnet 5.5).
- Model time: change 1 6:12, change 2 6:38, change 3 until the failure about 4 minutes, test fix 5:35, tests and deployment 0:30.

## Open after this session

- Nothing for the code. The video files live outside the repo.
