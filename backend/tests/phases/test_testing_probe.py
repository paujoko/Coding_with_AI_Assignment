"""P5 Testing, action `probe`: Wings injects small bugs into the code and reports which ones the tests caught."""

import pytest
from pydantic import ValidationError

from wings.adapters.sandbox import LocalSandbox
from wings.application.ports import ProcessResult
from wings.domain.artifacts import ArtifactKind
from wings.domain.errors import InvalidTransitionError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus
from wings.domain.trace import strength_results

TESTS = ["test_req_001_add", "test_req_002_list", "test_req_003_done", "test_plain_helper"]


def junit(failing: tuple[str, ...] = ()) -> str:
    cases = "".join(
        f'<testcase classname="tests.test_tasks" name="{name}">' + ('<failure message="assert False">boom</failure>' if name in failing else "") + "</testcase>"
        for name in TESTS
    )
    return f'<testsuites><testsuite name="pytest" tests="{len(TESTS)}">{cases}</testsuite></testsuites>'


COLLECTION_ERROR = '<testsuites><testsuite name="pytest" errors="1" tests="1"><testcase classname="" name="tests.test_tasks"><error message="collection failure">ImportError</error></testcase></testsuite></testsuites>'


class ScriptedSandbox:
    """Stands in for the real sandbox: the first run is the developer's green run (and any run after
    `next_green` is set), every other run takes the next entry of `script`."""

    def __init__(self, script: list[str]) -> None:
        self.script = list(script)
        self.calls: list[tuple[dict[str, str], float]] = []
        self.next_green = True
        self.scripted = 0

    def run(self, files, argv, timeout=60.0, collect=None, stdin=None) -> ProcessResult:
        self.calls.append((dict(files), timeout))
        if self.next_green:
            kind, self.next_green = "green", False
        else:
            kind = self.script[self.scripted % len(self.script)]
            self.scripted += 1
        if kind == "timeout":
            return ProcessResult(exit_code=124, output="Stopped", seconds=timeout, timed_out=True)
        if kind == "collection":
            return ProcessResult(exit_code=2, output="ImportError", seconds=0.2, collected={"wings-junit.xml": COLLECTION_ERROR})
        if kind == "no-report":
            return ProcessResult(exit_code=3, output="INTERNALERROR", seconds=0.2)
        failing = {"green": (), "survived": (), "caught": ("test_req_003_done", "test_plain_helper"), "caught-1": ("test_req_001_add",)}[kind]
        return ProcessResult(exit_code=1 if failing else 0, output="", seconds=0.5, collected={"wings-junit.xml": junit(failing)})


def ready(orch, walk, sandbox) -> str:
    """A project with code approved, tests written and run once in `sandbox`."""
    orch.sandbox = sandbox
    pid = walk(orch, P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    orch.approve(pid, P.CODEGEN)
    orch.run_action(pid, P.TESTING, "generate", {})
    orch.run_action(pid, P.TESTING, "run", {})
    return pid


def llm_calls(orch, pid) -> int:
    return sum(e.kind == "agent.llm_call" for e in orch.store.list_events(pid))


# The whole thing for real: the demo to-do program, real pytest runs in the local sandbox.


def test_bugs_are_injected_into_the_demo_program_and_the_real_tests_catch_them(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = ready(orch, walk, LocalSandbox())
    report_before = orch.store.get_artifact(pid, "test-report")
    calls_before = llm_calls(orch, pid)

    result = orch.run_action(pid, P.TESTING, "probe", {})

    assert llm_calls(orch, pid) == calls_before  # no model is asked
    artifact = orch.store.get_artifact(pid, "test-strength")
    assert artifact.kind is ArtifactKind.TEST_STRENGTH and artifact.author == "system:mutation"
    assert artifact.path == "reports/test-strength.md" and artifact.covers == [] and artifact.defines == []
    c = artifact.content
    assert c["total"] == 8 and c["caught"] + c["survived"] + c["invalid"] == 8
    assert c["invalid"] == 0 and c["caught"] >= 5
    assert c["score"] == pytest.approx(c["caught"] / (c["caught"] + c["survived"]), abs=1e-4)
    sources = {a.content["path"]: a.text for a in orch.store.list_artifacts(pid, P.CODEGEN) if a.kind is ArtifactKind.SOURCE_FILE}
    for m in c["mutants"]:
        assert sources[m["path"]].split("\n")[m["line"] - 1] == m["original"] != m["mutated"]
        assert bool(m["tests"]) == (m["outcome"] == "caught")
        assert "source" not in m
    # the classic bug of the demo: a task that never reaches the list is noticed by the tests of several requirements
    removed = next(m for m in c["mutants"] if m["description"] == "the call `tasks.append(task)` was removed")
    assert removed["outcome"] == "caught" and "test_req_001_add_task_to_empty_list" in removed["tests"] and "REQ-001" in removed["requirements"]
    assert set(c["by_requirement"]) == {f"REQ-00{i}" for i in range(1, 6)} and c["by_requirement"]["REQ-001"] >= 1
    assert result.outcome.reply.startswith(f"{c['caught']} of {c['caught'] + c['survived']} injected bugs caught")
    assert "# Test strength" in artifact.text

    # the entry point is not imported by any test: a bug there survives, and Wings offers a test for it
    survivor = next(m for m in c["mutants"] if m["outcome"] == "survived")
    assert survivor["path"] == "todo/__main__.py"
    assert f"todo/__main__.py line {survivor['line']}" in result.outcome.reply
    action = result.outcome.data["next_actions"][0]
    assert (action["phase"], action["action"]) == ("testing", "generate")
    assert "Add a test that fails" in action["input"]["guidance"] and f"todo/__main__.py line {survivor['line']}" in action["input"]["guidance"]

    # the test results are untouched, the trace does not take the report for coverage, and it is fresh
    assert orch.store.get_artifact(pid, "test-report").revision == report_before.revision
    trace = orch.trace(pid)
    assert all("test-strength" not in ids for ids in trace.covered.values())
    view = orch.trace_view(pid)
    assert view.strength is not None and view.strength["caught"] == c["caught"] and view.results["REQ-001"] == "passed"
    orch.approve(pid, P.TESTING)  # the approval gate still only asks for the green run


# Outcomes, with scripted runs (fast and exact)


def test_each_run_is_judged_caught_survived_or_invalid(make_orchestrator, demo_script, walk):
    sandbox = ScriptedSandbox(["caught", "survived", "timeout", "collection", "caught-1", "no-report"])
    orch = make_orchestrator(demo_script)
    pid = ready(orch, walk, sandbox)
    result = orch.run_action(pid, P.TESTING, "probe", {"limit": 6})
    c = orch.store.get_artifact(pid, "test-strength").content
    assert [m["outcome"] for m in c["mutants"]] == ["caught", "survived", "invalid", "invalid", "caught", "invalid"]
    assert (c["caught"], c["survived"], c["invalid"], c["total"]) == (2, 1, 3, 6)
    assert c["score"] == pytest.approx(2 / 3, abs=1e-4)  # invalid runs count for neither side
    first = c["mutants"][0]
    assert first["tests"] == ["test_req_003_done", "test_plain_helper"] and first["requirements"] == ["REQ-003"]
    assert "time limit" in c["mutants"][2]["reason"] and "before any test" in c["mutants"][3]["reason"]
    assert c["by_requirement"] == {"REQ-001": 1, "REQ-002": 0, "REQ-003": 1}
    assert result.outcome.reply.startswith("2 of 3 injected bugs caught (3 not counted).")
    survivor = c["mutants"][1]
    assert f"Survived: {survivor['path']} line {survivor['line']} ({survivor['description']})" in result.outcome.reply
    assert result.outcome.data["strength"] == {k: c[k] for k in ("caught", "survived", "invalid", "total", "score")}
    assert result.outcome.data["checked_by"] == "code"
    assert [a["action"] for a in result.outcome.data["next_actions"]] == ["generate"]
    assert orch.project(pid).status(P.TESTING) is PhaseStatus.DRAFT


def test_every_run_changes_exactly_one_source_line_and_has_its_own_time_limit(make_orchestrator, demo_script, walk):
    sandbox = ScriptedSandbox(["caught"])
    orch = make_orchestrator(demo_script)
    pid = ready(orch, walk, sandbox)
    orch.run_action(pid, P.TESTING, "probe", {"limit": 5})
    (original, run_timeout), probes = sandbox.calls[0], sandbox.calls[1:]
    assert len(probes) == 5
    mutants = orch.store.get_artifact(pid, "test-strength").content["mutants"]
    for (files, timeout), m in zip(probes, mutants):
        assert files.keys() == original.keys()
        changed = [path for path in files if files[path] != original[path]]
        assert changed == [m["path"]] and not m["path"].startswith("tests/")
        before, after = original[m["path"]].split("\n"), files[m["path"]].split("\n")
        assert [i + 1 for i, (x, y) in enumerate(zip(before, after)) if x != y] == [m["line"]] and len(before) == len(after)
        assert 10.0 <= timeout < run_timeout  # an endless loop costs seconds, not the two minutes of a full run


def test_all_bugs_caught_needs_no_next_step(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = ready(orch, walk, ScriptedSandbox(["caught"]))
    result = orch.run_action(pid, P.TESTING, "probe", {"limit": 3})
    assert result.outcome.reply.startswith("3 of 3 injected bugs caught.") and "Survived" not in result.outcome.reply
    assert result.outcome.data["next_actions"] == []


def test_the_limit_is_an_input_between_1_and_20(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = ready(orch, walk, ScriptedSandbox(["caught"]))
    for bad in (0, 21):
        with pytest.raises(ValidationError):
            orch.run_action(pid, P.TESTING, "probe", {"limit": bad})
    orch.run_action(pid, P.TESTING, "probe", {"limit": 20})
    assert orch.store.get_artifact(pid, "test-strength").content["total"] == 20
    spec = next(a for a in orch.registry.get(P.TESTING).actions if a.name == "probe")
    assert spec.label == "Inject bugs" and spec.input_model.model_json_schema()["properties"]["limit"]["default"] == 8


# The gate: only a green run on the current code and tests says anything.


def test_bugs_are_injected_only_after_a_green_and_current_run(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = walk(orch, P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    orch.approve(pid, P.CODEGEN)
    with pytest.raises(InvalidTransitionError, match="no tests"):
        orch.run_action(pid, P.TESTING, "probe", {})
    orch.run_action(pid, P.TESTING, "generate", {})
    with pytest.raises(InvalidTransitionError, match="sandbox"):
        orch.run_action(pid, P.TESTING, "probe", {})
    sandbox = ScriptedSandbox(["caught"])
    orch.sandbox = sandbox
    with pytest.raises(InvalidTransitionError, match="Run the tests first"):
        orch.run_action(pid, P.TESTING, "probe", {})
    orch.run_action(pid, P.TESTING, "run", {})

    service = orch.store.get_artifact(pid, "source-todo-service-py")
    orch.update_artifact(pid, service.id, text=service.text + "\n")
    orch.approve(pid, P.CODEGEN)
    with pytest.raises(InvalidTransitionError, match="changed since the last run"):
        orch.run_action(pid, P.TESTING, "probe", {})
    assert len(sandbox.calls) == 1  # nothing ran

    orch.run_action(pid, P.TESTING, "run", {})  # scripted: this run fails two tests
    assert not orch.store.get_artifact(pid, "test-report").content["green"]
    with pytest.raises(InvalidTransitionError, match="do not pass"):
        orch.run_action(pid, P.TESTING, "probe", {})
    assert len(sandbox.calls) == 2
    assert all(a.id != "test-strength" for a in orch.store.list_artifacts(pid, P.TESTING))


def test_the_result_goes_out_of_date_with_code_and_tests_like_the_test_report(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = ready(orch, walk, ScriptedSandbox(["caught", "survived"]))
    assert strength_results(orch.store.list_artifacts(pid)) is None  # never checked
    orch.run_action(pid, P.TESTING, "probe", {"limit": 4})
    fresh = strength_results(orch.store.list_artifacts(pid))
    assert fresh is not None and (fresh["caught"], fresh["survived"], fresh["score"]) == (2, 2, 0.5)
    assert set(fresh) == {"caught", "survived", "invalid", "total", "score", "by_requirement"}

    test_file = orch.store.get_artifact(pid, "test-test-tasks-py")
    orch.update_artifact(pid, test_file.id, text=test_file.text + "\n")
    assert strength_results(orch.store.list_artifacts(pid)) is None  # the tests changed
    assert orch.trace_view(pid).strength is None
    orch.sandbox.next_green = True
    orch.run_action(pid, P.TESTING, "run", {})
    assert strength_results(orch.store.list_artifacts(pid)) is None  # a new run is not a new check
    orch.run_action(pid, P.TESTING, "probe", {"limit": 4})
    assert strength_results(orch.store.list_artifacts(pid)) is not None

    service = orch.store.get_artifact(pid, "source-todo-service-py")
    orch.update_artifact(pid, service.id, text=service.text + "\n")
    assert strength_results(orch.store.list_artifacts(pid)) is None  # the code changed
