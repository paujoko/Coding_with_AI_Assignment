# P5 Testing

**Requirement (PDF, P5):** generate tests, run them, report results. Tests come from requirements and design, not only from code. On failure, explain why, propose a fix, re-run.

**How it works**

- `generate {depth, guidance}`: the `tester` (mid, no tools) writes pytest files under `tests/` from the acceptance criteria; test names carry the requirement (`test_req_003_complete_a_task`). Files must parse. `depth` is `focused` (default, about one test per criterion) or `thorough`; the wing caps the number of tests from the acceptance criteria (`schema.py: test_limit`: focused criteria + 2 within 6 to 20, thorough twice the criteria + 4 within 12 to 50) and refuses more, so the model retries. Without `depth` the last one is kept (`content.depth` of `test-gaps`). The prompt forbids large data, sleeps and real servers unless a requirement is about serving pages (ADR 0018).
- `gaps`: the tester lists every requirement its tests do not check fully (artifact `test-gaps`, saved on every generation).
- `run`: code and tests run for real in the Sandbox (`pytest --junitxml`). The JUnit XML gives each outcome (`domain/testreport.py`); nothing comes from a model. Artifact `test-report` with counts, per-test results and `verified` (REQ id -> worst outcome, then `apply_gaps`: a tester's gap turns `passed` into `partial`, a coder's deviation gives `not_met`; only `passed` counts as verified).
- `probe {limit}` ("Inject bugs"): only after a green run on the current code and tests. `domain/mutation.py` picks `limit` small bugs (default 8, at most 20; deterministic, one changed line each), the tests run once per bug in the Sandbox, and the artifact `test-strength` (`reports/test-strength.md`, author `system:mutation`) says per bug: `caught` (which tests failed, which REQ ids), `survived` (all tests passed) or `invalid` (the run stopped before the tests or hit the time limit; not counted). Score = caught / (caught + survived). No model is asked. A surviving bug becomes a next step that opens `generate` with guidance for the missing test. The result goes out of date with code and tests like the test report (`domain/trace.py: strength_results`). Details: `docs/code/wings.md`, "Injected bugs".
- `explain`: the `debugger` (frontier) reads the failures, the tests and the code, and says which one is wrong. A wrong test is fixed in this phase (new test revisions, run again). A code bug becomes a next step "Send the fix to Code generation" (codegen `revise` with the fix filled in).
- `discuss {question}`.

**Demo for C7:** `probe` on the demo to-do program injects 8 bugs and reports which ones the generated tests catch (`tests/phases/test_testing_probe.py`, real pytest runs). `tests/phases/test_testing.py` injects one bug by hand, shows a test failing, sends the fix to code generation and shows the tests passing again.

**Limits:** the Sandbox runs with the developer's user rights (ADR 0013). Timeout 120 s per run; per injected bug four times the last green run, at least 10 s. `probe` saves an artifact, so on an approved phase it reopens the phase (run it before approving). Surviving bugs can be equivalent changes that no test could catch.

**Grading hooks:** C1, C7.
