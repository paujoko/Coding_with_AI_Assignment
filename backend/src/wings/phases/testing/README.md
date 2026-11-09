# P5 Testing

**Requirement (PDF, P5):** generate tests, run them, report results. Tests come from requirements and design, not only from code. On failure, explain why, propose a fix, re-run.

**How it works**

- `generate {guidance}`: the `tester` (mid) writes pytest files under `tests/` from the acceptance criteria; test names carry the requirement (`test_req_003_complete_a_task`). Files must parse.
- `run`: code and tests run for real in the Sandbox (`pytest --junitxml`). The JUnit XML gives each outcome (`domain/testreport.py`); nothing comes from a model. Artifact `test-report` with counts, per-test results and `verified` (REQ id -> worst outcome).
- `explain`: the `debugger` (frontier) reads the failures, the tests and the code, and says which one is wrong. A wrong test is fixed in this phase (new test revisions, run again). A code bug becomes a next step "Send the fix to Code generation" (codegen `revise` with the fix filled in).
- `discuss {question}`.

**Demo for C7:** `tests/phases/test_testing.py` injects a bug into the generated code, shows a test failing, sends the fix to code generation and shows the tests passing again.

**Limits:** the Sandbox runs with the developer's user rights (ADR 0013). Timeout 120 s per run.

**Grading hooks:** C1, C7.
