# P5 Testing (planned)

**Requirement (PDF, P5):** generate tests, run them, report results. Tests come from requirements and design (one per use case, scenarios from sequence diagrams), not only from code. On failure, explain why, propose a fix, re-run.

**Suggested design**

- Agents: `tester` (writes pytest tests from acceptance criteria; test names carry the REQ id, e.g. `test_req_003_add_task`), `debugger` (reads a failing run and proposes a fix to code or test, saying which one is wrong).
- New port `TestRunner.run(workspace_path) -> TestReport`, adapter: pytest in a subprocess (later in a container). Deterministic: the result comes from pytest, never from the LLM.
- Actions: `generate`, `run`, `explain_failure {test_id}`, `apply_fix`.
- Demo requirement (C7): show a generated test failing on an injected bug and passing after the fix.

**Grading hooks:** C1, C7.
