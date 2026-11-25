# 0020 JavaScript tests run with Node's built-in runner; the test gate says how much is verified

- Date: 2026-11-25
- Status: accepted (partly supersedes ADR 0014: the rejected option "generate JavaScript and check it like Python" is now taken for tests, not for the design check)
- Decided by: Paul (JavaScript tests must be built, 2026-11-25); built by Claude Code (Opus 5.5) as a subagent on branch `demo/tests`

## Context

A real run on 2026-11-25 (Flappy Bird on DeepSeek V4.1 Flash) ended with 49 green tests, and only REQ-001 of 19 requirements had a passing test. The whole game logic was in `game.js`. Wings generated and ran only pytest, so REQ-002 to REQ-013 got no test result at all. Testing could still be approved, and an approved Tests step looked like "everything checked".

Both halves of the problem were our own decisions. ADR 0014 kept generated logic in Python and rejected "generate JavaScript and check it like Python" as too much for the course. The approval gate (ADR 0013, s03) asked only for a green run on the current code; it never said how many requirements that run covers. A browser game cannot keep its rules in Python, so the first half breaks as soon as a developer asks for one.

## Decision

1. **JavaScript tests use Node's built-in test runner.** The tester may write `tests/<name>.test.js` (or `.test.mjs`, `.test.cjs`) next to the pytest files, with `require("node:test")` and `require("node:assert/strict")`. No npm packages: the test file schema refuses a file that loads anything but Node's own modules and project files, and one that does not use `node:test`. Tests check exported logic, never the DOM or a browser.
2. **Logic must be importable, else it is a declared gap.** Wings finds by code which JavaScript files Node can import (`domain/nodetest.py: js_exports`, CommonJS `module.exports` or ES `export`) and tells the tester. A file that exports nothing (a page script) cannot be tested this way; the tester lists its requirements in `gaps` instead of copying its code into a test (ADR 0014 style). The coder prompt gets one rule: browser logic goes into its own `.js` file that does not touch the page or start a timer when loaded and ends with `if (typeof module !== "undefined" && module.exports) { module.exports = { ... }; }`. We chose this guard over ES modules because it works with a plain `<script>` in the browser and with `require` in every Node version, and the codegen wing does not have to allow `.mjs` files.
3. **The sandbox runs Node next to pytest.** `{node}` in a sandbox command is the `node` on the PATH; a missing program comes back as `not_found`. P5 runs pytest as before, then `node --test --test-reporter=tap --test-timeout=30000 --test-force-exit <file>` once per JavaScript test file, with 60 s per file (`JS_FILE_TIMEOUT`). One run per file, because Node's TAP output does not name the file of a passing test, and a file that hangs in synchronous code loses all its results (Node reports a file's tests when the file ends). `domain/nodetest.py: parse_tap` reads the TAP into the same `TestResult` as pytest (`runner: "node"`), with nested `describe` names joined by " > ", the requirement from the name or the enclosing block (`REQ-003 ...`; the id pattern now accepts a dash), and the project lines of each failure. A file Node cannot load is one error with the reason (`ReferenceError: document is not defined`) and its lines. The fix loop of ADR 0019 is unchanged: JavaScript failures carry `where` lines like pytest failures and go to the debugger the same way.
4. **No node, no pass.** Without node (or with a node older than 20.14, which lacks `--test-force-exit`) every JavaScript test file is one `skipped` result "JS tests not run: node not found". Its requirements get no `passed` verdict. This does not block approval by itself, because the count below says what was not checked.
5. **The gate says how much is verified (A6).** Every test run computes `domain/testreport.py: verification` over all requirements the requirements define: verified by a passing test, without a test result, only partly tested, not met by the code, with failing tests, with skipped tests only. The summary ("3 of 19 requirements verified by a passing test; 12 without a test result.") is stored in the test report (`content.verification`), stands in the reply and in `reports/test-results.md`, in the marked sentence of the Tests screen (with the ids per reason below it), next to the Accept button, and in the `phase.approved` event (`PhaseModule.approval_note`, so CLI, MCP, a carried change and catch-up log it too).
6. **`not_met` does not block approval.** The existing rule stays: the tests must have run green on the current code and tests. A requirement the coder declared as not met, or one without a test, is said with the count, and the developer decides. Reason: a blocking rule would make every deviation (often a platform limit the developer already accepted in P1) a dead end, and the developer could only get past it by editing the declaration. The count makes the decision visible instead of hiding it behind a green check.

Rejected:

- **A browser test runner (Playwright, jsdom).** npm packages and a browser in the developer's environment; slow; and the logic is what the requirements are about, not the drawing.
- **`--test-reporter=junit` and the existing JUnit parser.** A newer reporter than TAP, and in our trial (Node 24) it dropped the stderr of a file that cannot load, which is the most useful line in the Flappy Bird case. TAP has been built in since the runner left its experimental phase.
- **One Node run for all files.** Faster by a fraction of a second per file, but results lose their file and one hanging file loses everything.
- **Evaluate a page script in a fake `window` (vm, jsdom).** That tests a copy of the browser, not the program; ADR 0014 says to declare such gaps.
- **Block approval while a requirement is `not_met` or has no test.** See point 6.
- **Mutation testing for JavaScript.** "Inject bugs" stays Python only (`domain/mutation.py` uses `ast`).

## Consequences

- A web game's rules can be verified, and the trace, the consistency check and the gate count them like Python tests.
- The code generation wing still does not compare JavaScript with the class diagram; only tests check it.
- Node 20.14 or newer must be on the PATH for JavaScript tests (the version that, as far as we know, added `--test-force-exit`; only Node 24.12 was tried). Without it, the run says so and the JavaScript requirements stay unverified.
- The scripted mock exercises the path: "web view" in the code step adds `todo/static/tasks.js` (exports, tested with two Node tests) and `todo/static/page.js` (a page script; the tester declares REQ-002 as only partly testable). The default demo is unchanged.
- Not checked with a real model: whether DeepSeek follows the export rule and writes `node:test` files that pass the schema on the first try. That needs a paid run by a person.
- No API DTO changed (`api_version` stays 11); the test report's content gained `verification`, `node` and `runner` per test, mirrored in `frontend/src/api/types.ts`.
