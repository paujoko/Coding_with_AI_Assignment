"""P5 Testing: few, focused, fast tests (real run 2026-11-25: the tester took almost four minutes with
eleven check_python calls, and one test seeded 10,000 rows, which pushed pytest over its time limit)."""

import copy

import pytest

from wings.application.orchestrator import ActionFailedError
from wings.domain.phases import PhaseId as P
from wings.phases.testing.module import GenerateInput
from wings.phases.testing.schema import TestFile, count_tests, test_limit


def coded(orch, walk) -> str:
    pid = walk(orch, P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    orch.approve(pid, P.CODEGEN)
    return pid


def asks_of_tester(orch):
    return [c for c in orch.llm.calls if c.agent == "tester" and c.json_mode]


def text_of(call) -> str:
    return "\n".join(t.content or "" for t in call.messages)


def test_focused_is_the_default_depth():
    assert GenerateInput().depth == "focused"
    assert GenerateInput.model_json_schema()["properties"]["depth"]["enum"] == ["focused", "thorough"]


def test_the_limit_follows_the_acceptance_criteria_within_bounds():
    assert test_limit(7, "focused") == 9
    assert test_limit(1, "focused") == 6
    assert test_limit(100, "focused") == 20
    assert test_limit(7, "thorough") == 18
    assert test_limit(100, "thorough") == 50


def test_count_tests_counts_functions_and_methods_pytest_collects():
    f = TestFile(path="tests/test_a.py", purpose="", content="def test_a():\n    pass\n\ndef helper():\n    pass\n\nclass TestB:\n    def test_c(self):\n        pass\n")
    assert count_tests([f]) == 2


def test_the_tester_works_without_tool_rounds_and_is_told_the_limit(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = coded(orch, walk)
    orch.llm.calls.clear()
    result = orch.run_action(pid, P.TESTING, "generate", {})
    calls = asks_of_tester(orch)
    assert len(calls) == 1 and calls[0].tools == []
    # the demo requirements have 7 acceptance criteria
    assert "Focused tests: write at most 9 tests" in text_of(calls[0])
    assert result.outcome.reply.startswith("7 test(s) in 1 file(s).")


def test_too_many_tests_are_refused_and_the_tester_tries_again(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    good = script["tester"][0]
    many = copy.deepcopy(good)
    many["files"][0]["content"] += "".join(f"\n\ndef test_req_001_extra_{i}():\n    assert True\n" for i in range(5))  # 12 > 9
    script["tester"] = [many, good]
    orch = make_orchestrator(script)
    pid = coded(orch, walk)
    orch.llm.calls.clear()
    result = orch.run_action(pid, P.TESTING, "generate", {})
    assert len(asks_of_tester(orch)) == 2
    assert "at most 9 are allowed" in text_of(asks_of_tester(orch)[1])
    assert result.outcome.reply.startswith("7 test(s)")

    script["tester"] = [many]
    orch = make_orchestrator(script)
    pid = coded(orch, walk)
    with pytest.raises(ActionFailedError, match="at most 9"):
        orch.run_action(pid, P.TESTING, "generate", {})


def test_writing_again_without_a_depth_keeps_the_last_one(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = coded(orch, walk)
    orch.run_action(pid, P.TESTING, "generate", {"depth": "thorough"})
    orch.run_action(pid, P.TESTING, "generate", {"guidance": "Also check an empty title"})
    assert "Thorough tests: write at most 18 tests" in text_of(asks_of_tester(orch)[-1])
    orch.run_action(pid, P.TESTING, "generate", {"depth": "focused", "guidance": "fewer"})
    assert "Focused tests: write at most 9 tests" in text_of(asks_of_tester(orch)[-1])


def test_the_coder_compares_with_the_design_but_no_longer_spends_rounds_on_parsing(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = walk(orch, P.CODEGEN)
    orch.llm.calls.clear()
    orch.run_action(pid, P.CODEGEN, "generate", {})
    coder = [c for c in orch.llm.calls if c.agent == "coder"]
    assert {t.name for t in coder[0].tools} == {"compare_with_design"}
