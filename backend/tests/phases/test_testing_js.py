"""P5 Testing with JavaScript (ADR 0020): node:test files next to pytest, run for real, and an honest count.

Real run 2026-11-25 (Flappy Bird on DeepSeek): the game logic was all in game.js, Wings generated and ran
only pytest, 49 tests were green, and only REQ-001 of 19 requirements had a passing test. Testing could be
approved and looked checked. The demo script has the same shape in small: "web view" in the code step adds
todo/static/tasks.js (exports) and page.js (a page script Node cannot load).
"""

import copy
import shutil

import pytest
from pydantic import ValidationError

from wings.adapters.sandbox import LocalSandbox
from wings.application.ports import ProcessResult
from wings.domain.phases import PhaseId as P
from wings.phases.testing import module as testing_module
from wings.phases.testing.schema import TestFile, count_tests

NODE = shutil.which("node") is not None
needs_node = pytest.mark.skipif(not NODE, reason="node is not installed")
WEB_VIEW = {"feedback": "Add a small web view of the list; keep its formatting in JavaScript."}


class NoNode(LocalSandbox):
    """A machine without node: every "{node}" run is not found, Python runs as usual."""

    def run(self, files, argv, timeout=60.0, collect=None, stdin=None) -> ProcessResult:
        if "{node}" in argv:
            return ProcessResult(exit_code=127, output="node not found on the PATH", not_found=True)
        return super().run(files, argv, timeout, collect, stdin)


def web_view(orch, walk) -> str:
    pid = walk(orch, P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    orch.run_action(pid, P.CODEGEN, "revise", WEB_VIEW)
    orch.approve(pid, P.CODEGEN)
    return pid


@pytest.fixture
def orch(make_orchestrator, demo_script):
    o = make_orchestrator(demo_script)
    o.sandbox = LocalSandbox()
    return o


def test_the_tester_is_told_which_javascript_files_node_can_import(orch, walk):
    pid = web_view(orch, walk)
    written = orch.run_action(pid, P.TESTING, "generate", {})
    said = "\n".join(t.content or "" for t in orch.llm.calls[-1].messages)
    assert "todo/static/tasks.js: Node can import formatTask, listLines" in said
    assert "todo/static/page.js: Node cannot import it" in said
    js = next(a for a in written.outcome.artifacts if a.id == "test-tasks-test-js")
    assert js.content["language"] == "javascript" and js.path == "app/tests/tasks.test.js"


@needs_node
def test_javascript_tests_run_with_node_next_to_pytest_and_count_for_their_requirements(orch, walk):
    pid = web_view(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    result = orch.run_action(pid, P.TESTING, "run", {})
    report = orch.store.get_artifact(pid, "test-report").content
    node = [t for t in report["tests"] if t["runner"] == "node"]
    assert [t["name"] for t in node] == ["REQ-002 a task line shows number, title, due date and status", "REQ-002 an empty list says so"]
    assert all(t["outcome"] == "passed" and t["requirement"] == "REQ-002" and t["path"] == "tests/tasks.test.js" for t in node)
    assert report["green"] and report["passed"] == 9 and report["node"]["ran"] and report["node"]["files"] == 1
    # the tester declared that page.js cannot be tested, so REQ-002 is only partly verified
    assert report["verified"]["REQ-002"] == "partial"
    assert report["verification"]["summary"] == "4 of 5 requirements verified by a passing test; 1 only partly tested."
    assert "2 JavaScript tests ran with node" in result.outcome.reply and "4 of 5 requirements verified" in result.outcome.reply


@needs_node
def test_a_bug_in_the_javascript_fails_its_test_with_the_line(orch, walk):
    pid = web_view(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    tasks = orch.store.get_artifact(pid, "source-todo-static-tasks-js")
    orch.update_artifact(pid, tasks.id, text=tasks.text.replace('"done" : "open"', '"open" : "done"'))
    orch.approve(pid, P.CODEGEN)
    result = orch.run_action(pid, P.TESTING, "run", {})
    report = orch.store.get_artifact(pid, "test-report").content
    [failed] = [t for t in report["tests"] if t["outcome"] == "failed"]
    assert failed["runner"] == "node" and failed["requirement"] == "REQ-002" and not report["green"]
    assert failed["where"][-1]["path"] == "tests/tasks.test.js" and "formatTask" in failed["where"][-1]["code"]
    assert report["verified"]["REQ-002"] == "failed"
    assert result.outcome.data["next_actions"][0]["action"] == "explain"
    assert "tests/tasks.test.js:" in result.outcome.reply


def test_without_node_the_javascript_tests_are_not_run_and_never_passed(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    orch.sandbox = NoNode()
    pid = web_view(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    result = orch.run_action(pid, P.TESTING, "run", {})
    report = orch.store.get_artifact(pid, "test-report").content
    [js] = [t for t in report["tests"] if t["runner"] == "node"]
    assert js["outcome"] == "skipped" and js["message"] == "JS tests not run: node not found"
    assert report["node"] == {"ran": False, "files": 1, "reason": "node not found", "seconds": 0.0}
    assert "JS tests not run: node not found" in result.outcome.reply
    # pytest is green, so the gate holds; the count says what was not checked
    assert report["green"] and orch.registry.get(P.TESTING).approval_problem(orch.store.list_artifacts(pid)) is None


@needs_node
def test_a_javascript_test_that_never_ends_is_an_error_after_the_file_limit(orch, walk, demo_script, monkeypatch):
    monkeypatch.setattr(testing_module, "JS_FILE_TIMEOUT", 4.0)
    pid = web_view(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    test = orch.store.get_artifact(pid, "test-tasks-test-js")
    orch.update_artifact(pid, test.id, text=test.text.replace('assert.deepEqual(listLines([]), ["No tasks."]);', "while (true) {}"))
    orch.run_action(pid, P.TESTING, "run", {})
    report = orch.store.get_artifact(pid, "test-report").content
    [stuck] = [t for t in report["tests"] if t["runner"] == "node"]
    assert stuck["outcome"] == "error" and "4 s" in stuck["message"] and not report["green"]


def test_the_gate_shows_the_count_and_not_met_does_not_block(make_orchestrator, demo_script, walk):
    """ADR 0020: a requirement the coder declared as not met does not block approval; the count is said."""
    script = copy.deepcopy(demo_script)
    script["coder"] = [{**script["coder"][0], "deviations": [{"requirement": "REQ-005", "reason": "kept in memory only"}]}]
    orch = make_orchestrator(script)
    orch.sandbox = LocalSandbox()
    pid = walk(orch, P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    orch.approve(pid, P.CODEGEN)
    orch.run_action(pid, P.TESTING, "generate", {})
    orch.run_action(pid, P.TESTING, "run", {})
    summary = orch.store.get_artifact(pid, "test-report").content["verification"]["summary"]
    assert summary == "4 of 5 requirements verified by a passing test; 1 not met by the code."
    orch.approve(pid, P.TESTING)
    [event] = [e for e in orch.store.list_events(pid) if e.kind == "phase.approved" and e.phase == P.TESTING]
    assert summary in event.summary and event.data["note"] == summary
    assert orch.approval_note(pid, P.TESTING) == summary  # what the CLI and MCP print after approving


def test_node_test_files_are_checked_before_anything_runs():
    ok = "const test = require('node:test');\nconst { add } = require('../app/static/logic.js');\ntest('REQ-001 adds', () => {});\nit('two', () => {});\n"
    f = TestFile(path="tests/logic.test.js", purpose="x", content=ok)
    assert f.javascript and count_tests([f]) == 2
    assert TestFile(path="tests/logic.test.mjs", purpose="x", content="import test from 'node:test';\n").javascript
    with pytest.raises(ValidationError, match="npm|built-in modules"):
        TestFile(path="tests/logic.test.js", purpose="x", content="const test = require('node:test');\nconst { expect } = require('chai');\n")
    with pytest.raises(ValidationError, match="node:test"):
        TestFile(path="tests/logic.test.js", purpose="x", content="describe('x', () => { it('y', () => {}); });\n")
    with pytest.raises(ValidationError, match=r"\.test\.js"):
        TestFile(path="tests/logic.js", purpose="x", content="const test = require('node:test');\n")
