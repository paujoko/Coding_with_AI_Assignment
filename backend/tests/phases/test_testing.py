"""P5 Testing: tests from the requirements, run for real in the sandbox, failures explained."""

import copy

import pytest

from wings.adapters.sandbox import LocalSandbox
from wings.domain.errors import InvalidTransitionError
from wings.domain.phases import PhaseId as P


@pytest.fixture
def orch_with_sandbox(make_orchestrator, demo_script):
    def build(script=None):
        orch = make_orchestrator(script or demo_script)
        orch.sandbox = LocalSandbox()
        return orch

    return build


def coded(orch, walk):
    pid = walk(orch, P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    orch.approve(pid, P.CODEGEN)
    return pid


def test_tests_are_written_run_and_verify_requirements(orch_with_sandbox, walk):
    orch = orch_with_sandbox()
    pid = coded(orch, walk)
    written = orch.run_action(pid, P.TESTING, "generate", {})
    assert written.outcome.artifacts[0].id == "test-test-tasks-py"
    result = orch.run_action(pid, P.TESTING, "run", {})
    report = orch.store.get_artifact(pid, "test-report")
    assert report.content["green"] and report.content["passed"] == 7
    assert report.content["verified"] == {f"REQ-00{i}": "passed" for i in range(1, 6)}
    assert "All 7 tests pass" in result.outcome.reply


def test_an_injected_bug_fails_a_test_and_the_debugger_points_at_the_code(orch_with_sandbox, walk):
    orch = orch_with_sandbox()
    pid = coded(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    service = orch.store.get_artifact(pid, "source-todo-service-py")
    orch.update_artifact(pid, service.id, text=service.text.replace("        task.done = True\n", ""))
    orch.approve(pid, P.CODEGEN)
    result = orch.run_action(pid, P.TESTING, "run", {})
    report = orch.store.get_artifact(pid, "test-report")
    assert report.content["failed"] == 1 and report.content["verified"]["REQ-003"] == "failed"
    assert result.outcome.data["next_actions"][0]["action"] == "explain"

    explained = orch.run_action(pid, P.TESTING, "explain", {})
    action = explained.outcome.data["next_actions"][0]
    assert (action["phase"], action["action"]) == ("codegen", "revise") and "task.done = True" in action["input"]["feedback"]

    # The fix goes back through code generation; afterwards the tests are green again.
    orch.run_action(pid, P.CODEGEN, "revise", action["input"])
    orch.approve(pid, P.CODEGEN)
    orch.run_action(pid, P.TESTING, "run", {})
    assert orch.store.get_artifact(pid, "test-report").content["green"]


def test_a_wrong_test_is_fixed_in_the_testing_phase(orch_with_sandbox, demo_script, walk):
    script = copy.deepcopy(demo_script)
    good = script["tester"][0]["files"][0]
    bad = copy.deepcopy(good)
    bad["content"] = bad["content"].replace('== [("Buy milk", False)]', '== [("Buy milk", True)]')
    script["tester"] = [{**script["tester"][0], "files": [bad]}]
    script["debugger"] = [{"diagnosis": "The test expects a new task to be done.", "cause": "test", "fix": "Expect done to be False.", "test_files": [good]}]
    orch = orch_with_sandbox(script)
    pid = coded(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    assert not orch.run_action(pid, P.TESTING, "run", {}).outcome.data["verified"]["REQ-001"] == "passed"
    fixed = orch.run_action(pid, P.TESTING, "explain", {})
    assert fixed.outcome.data["cause"] == "test" and fixed.outcome.artifacts[0].author == "agent:debugger"
    orch.run_action(pid, P.TESTING, "run", {})
    assert orch.store.get_artifact(pid, "test-report").content["green"]


def test_running_needs_tests_and_a_sandbox(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)  # no sandbox
    pid = coded(orch, walk)
    with pytest.raises(InvalidTransitionError, match="no tests"):
        orch.run_action(pid, P.TESTING, "run", {})
    orch.run_action(pid, P.TESTING, "generate", {})
    with pytest.raises(InvalidTransitionError, match="sandbox"):
        orch.run_action(pid, P.TESTING, "run", {})


# Review round 7: approval needs a real, green, current run; results go out of date with the code.


def test_testing_is_approved_only_after_a_green_run_on_the_current_code(orch_with_sandbox, walk):
    from wings.domain.trace import test_results

    orch = orch_with_sandbox()
    pid = coded(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    with pytest.raises(InvalidTransitionError, match="Run the tests"):
        orch.approve(pid, P.TESTING)
    orch.run_action(pid, P.TESTING, "run", {})
    assert test_results(orch.store.list_artifacts(pid))["REQ-001"] == "passed"

    service = orch.store.get_artifact(pid, "source-todo-service-py")
    orch.update_artifact(pid, service.id, text=service.text + "\n")
    assert test_results(orch.store.list_artifacts(pid)) == {}  # the run says nothing about the new code
    orch.approve(pid, P.CODEGEN)
    with pytest.raises(InvalidTransitionError, match="changed since the last run"):
        orch.approve(pid, P.TESTING)

    orch.update_artifact(pid, service.id, text=service.text.replace("        task.done = True\n", ""))
    orch.approve(pid, P.CODEGEN)
    orch.run_action(pid, P.TESTING, "run", {})
    with pytest.raises(InvalidTransitionError, match="do not pass"):
        orch.approve(pid, P.TESTING)


def test_colliding_test_file_names_are_refused():
    from pydantic import ValidationError

    from wings.phases.testing.schema import TesterOutput

    body = "def test_req_001_x():\n    assert True\n"
    with pytest.raises(ValidationError, match="same file"):
        TesterOutput(notes="", files=[{"path": "tests/test_a.py", "purpose": "", "content": body}, {"path": "tests/test-a.py", "purpose": "", "content": body}])


def test_gaps_declared_by_coder_and_tester_are_not_shown_as_verified(orch_with_sandbox, demo_script, walk):
    script = copy.deepcopy(demo_script)
    script["coder"][0]["deviations"] = [{"requirement": "REQ-005", "reason": "not built"}]
    script["tester"][0]["gaps"] = [{"requirement": "REQ-004", "reason": "only partly testable"}]
    orch = orch_with_sandbox(script)
    pid = coded(orch, walk)
    written = orch.run_action(pid, P.TESTING, "generate", {})
    assert "REQ-004" in written.outcome.reply
    assert orch.store.get_artifact(pid, "test-gaps").content["gaps"][0]["requirement"] == "REQ-004"
    result = orch.run_action(pid, P.TESTING, "run", {})
    verified = orch.store.get_artifact(pid, "test-report").content["verified"]
    assert (verified["REQ-004"], verified["REQ-005"], verified["REQ-001"]) == ("partial", "not_met", "passed")
    assert "Verified: REQ-001, REQ-002, REQ-003." in result.outcome.reply
    assert "REQ-004" in result.outcome.reply and "REQ-005" in result.outcome.reply
    # a declared gap is not a link in the trace: it must not make a requirement look covered
    trace = orch.trace(pid)
    assert "test-gaps" not in trace.covered.get("REQ-004", []) and "code-gaps" not in trace.covered.get("REQ-005", [])


# Real run 2026-11-25 (expense tracker): a test seeded 10,000 rows, the run hit the 120 s limit, no JUnit
# file was written, and the debugger got "..F...F" plus 100,000 characters of code to guess from. Each
# explanation also started from zero, so fixes went in circles.


def failing_run(orch_with_sandbox, walk, script=None):
    """Tests written, then the bug from the demo: complete() no longer marks the task done."""
    orch = orch_with_sandbox(script)
    pid = coded(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    service = orch.store.get_artifact(pid, "source-todo-service-py")
    orch.update_artifact(pid, service.id, text=service.text.replace("        task.done = True\n", ""))
    orch.approve(pid, P.CODEGEN)
    return orch, pid


def line_of(orch, pid, artifact_id: str, code: str) -> int:
    return [line.strip() for line in orch.store.get_artifact(pid, artifact_id).text.splitlines()].index(code) + 1


def debugger_saw(orch) -> str:
    asked = [c for c in orch.llm.calls if c.agent == "debugger"][-1]
    return "\n".join(t.content or "" for t in asked.messages)


def test_a_failure_names_the_file_line_and_code_of_the_failing_check(orch_with_sandbox, walk):
    orch, pid = failing_run(orch_with_sandbox, walk)
    result = orch.run_action(pid, P.TESTING, "run", {})
    line = line_of(orch, pid, "test-test-tasks-py", "assert service.list()[0].done")
    [failed] = [t for t in orch.store.get_artifact(pid, "test-report").content["tests"] if t["outcome"] == "failed"]
    assert failed["path"] == "tests/test_tasks.py"
    assert failed["where"][-1] == {"path": "tests/test_tasks.py", "line": line, "code": "assert service.list()[0].done"}
    assert f"test_req_003_complete_a_task (tests/test_tasks.py:{line})" in result.outcome.reply


def test_the_debugger_gets_the_failing_lines_first_and_only_the_test_files_that_failed(orch_with_sandbox, demo_script, walk):
    script = copy.deepcopy(demo_script)
    extra = {"path": "tests/test_other.py", "purpose": "unrelated", "covers": ["REQ-002"], "content": "def test_req_002_unrelated():\n    assert True\n"}
    script["tester"][0]["files"].append(extra)
    orch, pid = failing_run(orch_with_sandbox, walk, script)
    orch.run_action(pid, P.TESTING, "run", {})
    orch.run_action(pid, P.TESTING, "explain", {})
    said = debugger_saw(orch)
    line = line_of(orch, pid, "test-test-tasks-py", "assert service.list()[0].done")
    assert f"tests/test_tasks.py:{line}  assert service.list()[0].done" in said
    assert "### tests/test_tasks.py" in said and "### todo/service.py" in said  # the failing test file and all code
    assert "### tests/test_other.py" not in said and "tests/test_other.py" in said  # named, not shown


def test_the_code_fix_carries_the_failing_lines_and_later_explanations_know_the_earlier_attempts(orch_with_sandbox, walk):
    orch, pid = failing_run(orch_with_sandbox, walk)
    orch.run_action(pid, P.TESTING, "run", {})
    first = orch.run_action(pid, P.TESTING, "explain", {})
    feedback = first.outcome.data["next_actions"][0]["input"]["feedback"]
    assert "task.done = True" in feedback and "test_req_003_complete_a_task (tests/test_tasks.py:" in feedback
    assert "Attempt" not in debugger_saw(orch)  # nothing to remember yet

    # The developer does not apply the fix; the next run still fails, and the next explanation knows it.
    orch.run_action(pid, P.TESTING, "run", {})
    second = orch.run_action(pid, P.TESTING, "explain", {})
    said = debugger_saw(orch)
    assert "Attempt 1 (cause: code)" in said and "still failing: test_req_003_complete_a_task" in said
    log = orch.store.get_artifact(pid, "fix-log")
    assert [a["number"] for a in log.content["attempts"]] == [1, 2] and not log.retired
    assert "Earlier attempts" in second.outcome.data["next_actions"][0]["input"]["feedback"]

    # The fix goes through code generation; the green run closes the loop.
    orch.run_action(pid, P.CODEGEN, "revise", second.outcome.data["next_actions"][0]["input"])
    orch.approve(pid, P.CODEGEN)
    orch.run_action(pid, P.TESTING, "run", {})
    assert orch.store.get_artifact(pid, "test-report").content["green"]
    assert orch.store.get_artifact(pid, "fix-log").retired


def test_writing_the_tests_again_starts_a_new_fix_loop(orch_with_sandbox, walk):
    orch, pid = failing_run(orch_with_sandbox, walk)
    orch.run_action(pid, P.TESTING, "run", {})
    orch.run_action(pid, P.TESTING, "explain", {})
    orch.run_action(pid, P.TESTING, "generate", {})
    assert orch.store.get_artifact(pid, "fix-log").retired


def test_a_test_that_hangs_stops_the_run_early_and_is_named(orch_with_sandbox, demo_script, walk, monkeypatch):
    import wings.phases.testing.module as testing

    monkeypatch.setattr(testing, "TEST_LIMIT", 2.0)
    script = copy.deepcopy(demo_script)
    script["tester"][0]["files"][0]["content"] += "\n\ndef test_req_002_waits_forever():\n    import time\n    time.sleep(60)\n"
    orch = orch_with_sandbox(script)
    pid = coded(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    result = orch.run_action(pid, P.TESTING, "run", {})
    report = orch.store.get_artifact(pid, "test-report").content
    assert report["seconds"] < 30 and report["passed"] == 7 and not report["green"]
    [hung] = [t for t in report["tests"] if t["outcome"] == "error"]
    assert hung["name"] == "test_req_002_waits_forever" and "2 s" in hung["message"]
    assert hung["where"][0]["code"] == "def test_req_002_waits_forever():"
    assert "test_req_002_waits_forever" in result.outcome.reply


def test_a_test_file_that_cannot_be_imported_is_named_with_its_line(orch_with_sandbox, demo_script, walk):
    script = copy.deepcopy(demo_script)
    script["tester"][0]["files"][0]["content"] = "from todo.missing import Nothing\n" + script["tester"][0]["files"][0]["content"]
    orch = orch_with_sandbox(script)
    pid = coded(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {})
    result = orch.run_action(pid, P.TESTING, "run", {})
    [broken] = orch.store.get_artifact(pid, "test-report").content["tests"]
    assert (broken["name"], broken["outcome"]) == ("tests/test_tasks.py", "error") and "todo.missing" in broken["message"]
    assert broken["where"][0] == {"path": "tests/test_tasks.py", "line": 1, "code": "from todo.missing import Nothing"}
    assert "tests/test_tasks.py:1" in result.outcome.reply
