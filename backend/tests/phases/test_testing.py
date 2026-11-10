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
