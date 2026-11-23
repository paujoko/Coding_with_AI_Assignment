# Session 2026-11-23 s06: change propagation, injected bugs, run guide, readable UI

- **Who:** Paul, Claude Code (Fable 5.2) in the desktop app on Paul's machine, coordinating seven subagents
- **When:** about 10:45 to 13:20 (local time)
- **Commits:** 5dcd811 .. (this commit), branch `feature/ux-overhaul`

## Goal

Review the whole project against the course brief a week before the presentation (30.11.), test it in the browser, and fix what blocks a good grade: change propagation (C2), tests that catch bugs (C7), a requirement followed end to end (C5), an intuitive start and a readable interface (C3).

## Human prompts (verbatim)

> Ok überarbeite nichmals das gnaze projekt, teste es selbst im frontend schaue was funktioniert und was nicht, überlege dir acuh wie man das forntend noch intuitiver, schöner machen kann, nutzte für das den impecable skill, überlege dir was am code man noch verbessern kann, oder ausbauen kann, überlege dir auch nich den uniquiness faktor ich glaube gemäss aufgabenstellung , shcuae vorallem auch das der start intuitiver ist, dass man den folder imemr angeben muss, dass es gneau beschirbet mit kopierbarem terminal link wie man die anwendung starten kann, mache die maintainance intuitiver, allgemein mache den generierten Text grösser besser lesbar, udn nehem unnötigen Text heraus, also anweisungen die eh niemend liest etc. Mache es subagent getireben dass du in kurzer Zeit viel ändern kannst, ich gebe dir komplette freiheit, ich möchte über nichts entscheiden müssen und vertraue dir komplett, mache es einfach auf einem neuen branch so dass ich es vor dem merge anscheun kann, schaue ob Linus mitlerweile eine neue version auf git gepusht hat, fals nicht mache mit dem jetztigen stand weiter

Earlier the same day: "wo kann ich jetzt mein projekt anscheun starten" (where can I start my project now), after a finished deployment.

## What was done

| Time | Step | By | Result |
|---|---|---|---|
| 10:45 | Fetch: nothing new from Linus since 851ee77; branch `feature/ux-overhaul`; Windows test fixes committed | Claude | 5dcd811 |
| 10:50 | Whole pipeline on the demo model in the browser (1440 px), every view looked at | Claude | findings below |
| 11:05 | Five subagents in parallel: store and sandbox robustness plus folder default; change propagation backend; injected bugs; run guide, drift, short replies; type scale, copy cut, start page | Claude, subagents | reports with tests per agent |
| 11:35 | Two frontend subagents: change tracker; Run it card, injected bugs view, requirement lens | subagents | 105 frontend tests |
| 12:00 | Merge of the follow-ups: `trace.strength` in the API, `ActionOutcome.changes_phase` (injecting bugs no longer reopens Testing), shorter testing and maintenance replies | Claude | ea5099e |
| 12:15 | Browser check of the new views on a fresh demo project; dock and composer overflow fixed; Maintenance runs its consistency check after a change; label "Step 2 of 6" | Claude | b21d4e9 |

## Decisions

- **Changes are carried through one phase per request** (`POST /changes/{n}/advance`), with an optional approval on the developer's behalf that is logged as such. The UI offers one step at a time by default and "Carry it through" as an explicit choice. ADR 0016.
- **Injected bugs (mutation testing) are computed by code** in the testing wing, with no model call; a timeout counts as "did not count", never as caught. ADR 0016.
- **A computed report about a phase does not change the phase** (`ActionOutcome.changes_phase = False`).
- **Every project has a folder**; without one the backend picks `~/WingsProjects/<slug>` (`WINGS_PROJECTS_DIR`).
- **The run guide is data, checked by code**: a start command whose module does not exist fails the deployment check.

## Problems and how they were found

| Problem | Found by | Fix |
|---|---|---|
| 500 on `GET /events` during an action: `PermissionError` reading `project.json` while another thread renamed it (Windows) | server log during the browser walk | reads under the store lock plus a bounded retry; hammer test |
| No diagrams drawn on Paul's machine although `tools/plantuml.jar` exists | browser walk; `.env` pointed to the folder before the move to `schule/` | a configured jar that does not exist falls back to the found one |
| Maintenance said "Start" forever; after a change nothing showed what was updated | browser walk | change tracker, receipt, sidebar progress |
| No way to see how to start the generated program | Paul's question after his own run | run guide artifact and Run it card |
| Next-step card and send button cut off at 1440 px | browser check after the subagents | grid columns `minmax(0, 1fr)` in dock and composer box |
| "Inject bugs" after approval reopened Testing and aged Deployment | subagent report, then a test | `changes_phase=False` |
| Sandbox grandchildren survived a timeout on Windows | existing test failing on Paul's machine | Windows job object plus taskkill |

## Verification

- Backend: full suite green on Windows (exit 0, about 440 tests), all on the scripted mock.
- Frontend: 105 tests, `tsc -b --noEmit` clean.
- Browser (demo model): start page with folder prefill, whole pipeline, Run it card, injected bugs (7 of 8 caught, 8.7 s), a change carried through all six steps in about 13 s with a receipt (11 updated, 4 added), requirement lens, 375 px without sideways scroll.
- Not verified: a real model run of the new flows (no paid calls), dark mode by eye, the Browse dialog.

## Open after this session

- Paul reviews the branch, then merge into `main` and push.
- A real run on DeepSeek before the presentation: change propagation and the run guide fields depend on the model following the new prompts.
- Mutation descriptions show raw backticks in the injected bugs view.

## Second round (same day): the Approve trap

Paul asked for a two-player mode in a real DeepSeek project. The requirements and design were revised; refinement, code, tests and deployment then showed "out of date" with an Approve button, and were approved one after another without being regenerated. The game stayed single-player, and Wings even showed the change as complete. Paul: "puh das ist absolut viel zu kompliziert ... man versteht viel zu wenig was wie zusammenhängt".

| Step | By | Result |
|---|---|---|
| Root cause from the project's own data (revisions, events) | Claude | the change ignored its planned phases; approving without a new revision counted as done |
| `POST /catch-up` (one stale phase per call, shared with `advance_change`), `stale` in the project view, completion only with a new revision after every changed upstream phase | backend subagent | tests from Paul's scenario first; full suite green |
| Text audit into three levels (must read, read when curious, only when asked); one status line and one primary action (`lib/next.ts`); out of date means Update, never Approve; replies and drift lists folded; auto-advance after Approve | frontend subagent | 154 frontend tests |
| Browser check of Paul's scenario on the demo model: five steps out of date, "Update all 5 steps", progress 2 of 5 with Stop, all green, code, tests and deployment at revision 2 with the priority | Claude | as intended |
