# 0019 Failure lines from a pytest plugin, and a memory for the fix loop

- Date: 2026-11-25
- Status: accepted
- Decided by: Claude Code (Opus 5.5) for Ben, session s09

## Context

A real run on 2026-11-25 (DeepSeek V4.1 Flash, an expense tracker, about 25 minutes) showed why fixing failed tests took so long and went in circles. The LLM log (`wings_llm.log`) gave the facts:

- One generated test seeded 10,000 rows one call at a time. The whole pytest run hit the 120 s limit, pytest was killed, and no JUnit XML was written. The report had no per-test results, and the debugger was told only "pytest could not run the tests" plus the dots and F's of the console.
- The debugger got about 100,000 characters (all tests, all code) and had to guess which tests failed and where. Its two calls took 112 s and 162 s.
- Each `explain` started from zero. Nothing told the debugger or the coder what the previous attempt had changed and whether it helped, so a fix could be undone by the next one. Ben: the time tracker "got lost in the tests".

## Decision

1. **Results come from a pytest plugin that writes as it goes.** Wings copies `phases/testing/pytest_events.py` into every test run (`-p _wings_events`). It writes one JSON line per event (test started, setup/call/teardown result, collection error) and flushes it at once. `domain/testreport.py: parse_events` turns the lines into the report. JUnit XML stays as the fallback.
2. **Every failure carries its lines.** The plugin records the traceback entries pytest already has (`reprtraceback.reprentries[].reprfileloc`), or the domain reads them from the traceback text. Only lines in the project's own files are kept, each with its source line (`where`: path, line, code, the line that raised last). The chat, the report view, the debugger and the coder all show `path:line`.
3. **A test that hangs ends the run early and is named.** A timer in the plugin ends the run when one test takes longer than 30 s (`TEST_LIMIT`). The event names the test; the report shows it as an error with the limit, pointing at its definition. A test that started but never finished because the whole run was stopped is an error too, so a stopped run is never green.
4. **The debugger sees less, in a better order.** First the failures with their lines, then the earlier attempts, then only the test files the failures run through (plus `conftest.py`; the others are named), then all the code. The code stays complete: the bug is often in code that is not on the traceback (a missing line).
5. **The fix loop has a memory.** `domain/fixloop.py: FixLog`, saved as the artifact `fix-log` (kind `fix_log`, a computed report, author `system:fixloop`). Each `explain` adds an attempt; the next `run` records what still fails after it. The history goes to the next `explain` and into the feedback for code generation, with the instruction not to repeat a fix that did not help, and with tests that failed after every attempt named as stuck. A green run or newly written tests retire the log. Explaining a code bug saves only this report, so it does not change the phase (`changes_phase=False`).

Rejected:

- **pytest-timeout or pytest-json-report.** Extra packages in the developer's environment; the plugin is about 80 lines of standard library.
- **Only a shorter overall time limit.** The run would still end without results.
- **Give the debugger a file-reading tool instead of the code.** Every tool round is another full model call; with DeepSeek that adds seconds to minutes. The code is sent once.
- **Keep the history in the chat.** The phase conversation mixes questions, answers and replies; the debugger needs the attempts and their measured effect, not prose.

## Consequences

- The probe ("Inject bugs") still judges by exit code and JUnit XML and does not load the plugin.
- A per-test limit ends the whole run; tests after the slow one are not reported in that run.
- Wings' own tests run real pytest through the plugin (`tests/phases/test_testing.py`), including a hanging test and a test file that cannot be imported.
- Not yet checked with a real model: whether DeepSeek uses the lines and the history as intended, and how much time it saves. That needs a paid run by a person.
