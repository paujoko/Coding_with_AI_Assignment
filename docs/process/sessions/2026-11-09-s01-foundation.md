# Session 2026-11-09 s01: foundation of the Wings environment

- **Who:** Paul (instructions), Claude Code with Opus 5.5 (design, code, tests, docs), one Claude Code subagent (independent review)
- **When:** 11:46 to about 12:30 (machine time, see `../README.md`)
- **Commits:** 0c2f8d4 .. (see `../timeline.md`)
- **Mode:** agentic coding. Claude planned, wrote files, ran tests, started the servers and clicked through the UI itself; Paul gave one instruction at the start.

## Goal

Lay the foundation of the environment: an architecture that is enforced, makes the wings easy to extend and to trigger directly, with P1 and P2 working end to end, plus two documentation folders and a `CLAUDE.md`.

## Human prompts (verbatim)

Earlier, on 2026-11-05, after the requirements PDF was summarised and a first architecture sketch shown:

> Bitte zeige mir mal eine architektur wei das ungefähr aussehen soll

The instruction for this session:

> Ok ich möchte dass du uns mal die Grundlage legst für das Projekt und das mal hin codest, dokumentiere alles ganz genau was du machst, vorallem auch dass es nachvillziebar ist wann du was gemacht hast, könnte später and der Präsi über wie wir programmiert haben wirhcitg werden, also lege 2 verschiedene Doku folder an einen für dokumentattion code, das hilft dir und neunen sessions den code zu verstehen und der 2te für coding prozess hier kommt alles heruein das wir später für die präsi bruahcne können zur dokumentiereung wie wir geradbeitet haben. èberlege dir hier sinnvolle struktur und erstelle ein Claude.md Dann nehme dir jetzt viel Zeit das ist wichtig, nutze bruanstorm, implementierungsplan, implemeniteren, testen, mögliches refactoring, für frontend nutzte impacable skill, beim backend entschiede dich für eine Architektur und schaue dass sie eingehalten wird, überlege welche architektur sinn ergibt, baue es so dass man vorallem die "Wings" sehr gut noch erweitern kann und geziehlt ansteuern kann, du baust erst mal das grundgerüst.

## What was done

| Time | Step | By | Result |
|---|---|---|---|
| 11:46 | Checked conventions, installed tools (Python 3.14, Node 24, Java 17, Docker), available skills | Claude | The requested "impeccable" frontend skill is not installed and not in the plugin catalog; used the `frontend-design` skill instead |
| 11:46 | Brainstorming done by Claude alone (Paul asked for the full pipeline), written as a design document | Claude | `specs/2026-11-09-foundation-design.md` |
| 11:47 | Implementation plan (11 tasks, global constraints, review focus) with the writing-plans skill | Claude | `plans/2026-11-09-foundation-plan.md` |
| 11:50 | Repo, `.gitignore`, architecture test before any code | Claude | 4 architecture tests |
| 11:51 | Domain layer, tests first | Claude | 16 then 19 tests |
| 11:53 | Ports, phase contract, LLM agent, registry, structured output | Claude | 27 tests |
| 11:54 | Adapters | Claude | 37 tests |
| 11:55 | Orchestrator | Claude | 45 tests |
| 11:58 | P1 and P2 wings, planned P3 to P7, bootstrap, demo mock script | Claude | 56 tests, all green on the first run |
| 12:00 | API and CLI; CLI smoke test revealed the mock bug; fixed | Claude | 61 tests |
| 12:00 to 12:09 | Frontend design plan, components, styles; checked in the browser at desktop and mobile width; five UI bugs fixed | Claude | 5 frontend tests, typecheck and build clean |
| 12:09 | Independent review dispatched to a fresh subagent | Claude | see below |
| 12:10 onwards | Code and process documentation, `CLAUDE.md`, README, ADRs | Claude | |

## Decisions

- Ports and adapters with a phase plugin registry, enforced by an `ast` test (ADR 0001).
- Python/FastAPI and React/TypeScript (ADR 0002).
- PlantUML as diagram notation, rendered by a backend port (ADR 0003).
- Scripted mock as the default LLM, OpenRouter for real runs, model tiers per agent (ADR 0004).
- Code-assigned stable `REQ-xxx` IDs and phase-level staleness (ADR 0005).
- Two documentation folders (ADR 0006).
- Reply selection of the mock by conversation stage instead of a call counter (bug fix, documented in `docs/code/llm.md`).
- Agents: analyst on the mid tier, architect on the frontier tier.
- Visual direction of the UI: the pipeline drawn as a wingspan (P1 to P3 left wing, P4 body, P5 to P7 right wing).

## Problems and how they were found

See `../lessons.md` (2026-11-09). In short: one backend bug found by a CLI smoke test, five frontend bugs found only by running the app in a browser, one tooling version clash found by the typechecker. None of them was caught by the unit tests that existed at the time.

## Verification

- Backend: 61 tests (architecture, domain, application, adapters, phases, API), no network.
- Frontend: 5 tests, `tsc` strict typecheck, production build.
- CLI: full P1 to P2 flow in separate processes against a temporary workspace.
- Browser (desktop 1366x860 and mobile 375x812): create project, Start, answer the three questions via chips, approve, generate design (coverage 5 of 5), edit a requirement, design turns "Out of date", activity log shows `phase.stale`; no horizontal scrolling on mobile.

## Numbers

- About 1,900 lines of backend code, 800 lines of backend tests, 2,000 lines of frontend code and styles (before docs).
- 9 commits in this session.

## Open after this session

- Partner reviews the architecture decisions (all are Claude's proposals so far).
- GitHub repository, PlantUML renderer, real-model run by Paul.
- Implement P3 refinement and P7 drift detection first (they carry C2 and C5).
