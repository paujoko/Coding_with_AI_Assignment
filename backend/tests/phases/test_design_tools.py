"""The architect checks its own design with deterministic tools before answering."""

import copy

from wings.domain.phases import PhaseId as P


def approved_requirements(orch):
    pid = orch.create_project("Todo").id
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "A todo app"})
    orch.run_action(pid, P.REQUIREMENTS, "answer", {"answers": "CLI"})
    orch.approve(pid, P.REQUIREMENTS)
    return pid


def test_architect_uses_tools_and_the_log_shows_them(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = approved_requirements(orch)
    orch.run_action(pid, P.DESIGN, "generate", {})
    used = [e for e in orch.store.list_events(pid) if e.kind == "agent.tool_call"]
    assert {e.data["tool"] for e in used} >= {"check_plantuml", "check_consistency", "check_coverage"}
    architect_calls = [c for c in orch.llm.calls if c.agent == "architect"]
    assert {t.name for t in architect_calls[0].tools} == {"check_plantuml", "check_consistency", "check_coverage"}
    assert architect_calls[-1].messages[-1].role == "tool"  # the answer came after the tool results


def test_inconsistent_design_is_reported_by_code_even_if_the_model_misses_it(make_orchestrator, demo_script):
    script = copy.deepcopy(demo_script)
    design = script["architect"][0]
    seq = next(d for d in design["diagrams"] if d["kind"] == "sequence")
    seq["plantuml"] = seq["plantuml"].replace("complete(1)", "finish(1)")
    orch = make_orchestrator(script)
    pid = approved_requirements(orch)
    result = orch.run_action(pid, P.DESIGN, "generate", {})
    assert "finish" in result.outcome.reply and "TaskService" in result.outcome.reply
    assert any("finish" in p for p in result.outcome.data["consistency"])
