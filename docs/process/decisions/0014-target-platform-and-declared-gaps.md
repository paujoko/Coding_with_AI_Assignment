# 0014 One target platform, said to every agent; gaps are declared and never count as verified

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) after Paul's first real run (session s03), on Paul's instruction to fix everything the run uncovered

## Context

Paul's first own run on DeepSeek V4.1 Flash ("tik tak toe app", answered "web app in the browser") went through P1 to P5 and broke in P6. Reading the run showed a deeper problem than the crash:

- The analyst offered "web app (HTML/CSS/JS)", "mobile app" and "desktop application" as options, although Wings can only generate and check Python. The requirements said "runs entirely in the browser with HTML/CSS/JS" (REQ-015, must).
- The architect designed a static browser app. The coder, whose prompt said "working Python code, standard library only", wrote a terminal program and did not mention the difference.
- The tester noticed ("the code renders to text instead of a DOM") and said in its notes that REQ-013 and REQ-015 could only partly be tested. Its test names still carried `req_015`, so the trace showed REQ-015 as verified by passing tests.
- Before that, the testing step had run twice: the first request took almost seven minutes, a second "Write tests" waited on the project lock and then ran again.

C7 (quality of the artefacts) and C2 (alignment under change) reward exactly the opposite: requirements that can be built, code that follows them, and verification that does not claim more than it checked.

## Decision

1. **One target platform, stated in every prompt.** Wings builds Python 3.12 programs with the standard library: a command-line program, or a local web app where a `http.server` started with `python -m <package>` serves HTML, CSS and JavaScript and keeps logic and data in Python. The analyst asks about the platform with buildable options only and records any difference as an assumption; the architect designs web apps as a Python server component plus browser pages; the coder may write `.html`, `.css`, `.js` and `.svg` files and gives a web server a `--check` option for the smoke run; the deployer can feed `smoke_input` to interactive programs.
2. **Gaps are declared, never silent.** The coder returns `deviations`, the tester returns `gaps`: requirement id and reason. Both are stored as artifacts of kind `known_gaps` (`code-gaps`, `test-gaps`) on every generation, also when empty, so an old declaration never outlives the files it was about. They carry no `covers`, so they cannot look like trace links.
3. **Verification is computed after the gaps.** `apply_gaps` turns a passing requirement with a tester's gap into `partial` and any requirement with a coder's deviation into `not_met`. Only `passed` counts as verified in the test report, the trace and the consistency check.
4. **One agent action per project at a time.** A second action while an agent works is refused with 409 instead of queued, and the project tells the UI what is running.
5. **The design gate.** P2 can be approved only when every functional requirement appears in at least one diagram.

Rejected: generating JavaScript and checking it like Python (needs a JS parser, a browser test runner and drift rules for a second language; too much for the course and outside "code generation earns the least"); hiding unbuildable options from the analyst without saying why (the developer would not understand why "mobile app" is missing).

## Consequences

- A developer who asks for something Wings cannot build sees it twice: as an assumption in the requirements and as a "not met" requirement after code generation. Green tests no longer hide it.
- Web apps keep every check working (classes, drift, pytest on the server side), but the JavaScript in the pages is neither compared with the design nor tested; this is listed as a limit in the codegen README.
- The gaps are declared by agents, so a model that does not declare one can still overclaim. Code catches what it can (tests must exist and pass), the declaration covers what code cannot see. This limit belongs in the report.
- API version 7 (`running`, the verdicts `partial` and `not_met`).
