import copy

import pytest

from wings.application.orchestrator import ActionFailedError
from wings.bootstrap import build_registry
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S


def approved_requirements(orch) -> str:
    pid = orch.create_project("Todo").id
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "todo"})
    orch.run_action(pid, P.REQUIREMENTS, "answer", {"answers": "cli"})
    orch.approve(pid, P.REQUIREMENTS)
    return pid


def test_generate_creates_diagrams_and_coverage(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = approved_requirements(orch)
    result = orch.run_action(pid, P.DESIGN, "generate", {})
    ids = [a.id for a in result.outcome.artifacts]
    assert ids == ["diagram-use-cases", "diagram-domain-classes", "diagram-complete-a-task"]
    assert result.outcome.artifacts[1].path == "design/domain-classes.puml"
    assert result.outcome.data["coverage"]["uncovered"] == []
    assert result.project.status(P.DESIGN) is S.DRAFT
    assert orch.trace(pid).ratio == 1.0


def test_uncovered_requirement_is_reported(make_orchestrator, demo_script):
    script = copy.deepcopy(demo_script)
    for d in script["architect"][0]["diagrams"]:
        d["covers"] = [c for c in d["covers"] if c != "REQ-004"]
    orch = make_orchestrator(script)
    pid = approved_requirements(orch)
    result = orch.run_action(pid, P.DESIGN, "generate", {})
    assert result.outcome.data["coverage"]["uncovered"] == ["REQ-004"]
    assert "REQ-004" in result.outcome.reply


def test_invalid_plantuml_fails_after_retry_and_saves_nothing(make_orchestrator, demo_script):
    script = copy.deepcopy(demo_script)
    script["architect"][0]["diagrams"][0]["plantuml"] = "graph TD; A-->B"
    orch = make_orchestrator(script)
    pid = approved_requirements(orch)
    with pytest.raises(ActionFailedError, match="startuml"):
        orch.run_action(pid, P.DESIGN, "generate", {})
    assert orch.store.list_artifacts(pid, P.DESIGN) == []
    # a tool round, the invalid answer, one retry
    assert len([c for c in orch.llm.calls if c.agent == "architect"]) == 3


def test_requirements_change_makes_design_stale(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = approved_requirements(orch)
    orch.run_action(pid, P.DESIGN, "generate", {})
    req = orch.store.get_artifact(pid, "requirements")
    _, stale = orch.update_artifact(pid, "requirements", content=req.content)
    assert stale == [P.DESIGN]
    assert orch.project(pid).status(P.DESIGN) is S.STALE


def test_developer_can_edit_diagram_source(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = approved_requirements(orch)
    orch.run_action(pid, P.DESIGN, "generate", {})
    edited, _ = orch.update_artifact(pid, "diagram-use-cases", text="@startuml\nactor Admin\n@enduml")
    assert edited.revision == 2 and edited.author == "developer" and "Admin" in edited.text
    with pytest.raises(ValueError):
        orch.update_artifact(pid, "diagram-use-cases", text="not uml")


def test_pipeline_registers_all_seven_wings_in_order_and_all_are_built():
    reg = build_registry()
    assert [m.id for m in reg.ordered()] == list(P)
    assert [m.implemented for m in reg.ordered()] == [True] * 7


def test_diagram_names_that_collide_get_distinct_ids(make_orchestrator, demo_script):
    # Review finding 6: "Use cases" and "Use-Cases" (or two non-Latin names) produced the same id.
    script = copy.deepcopy(demo_script)
    diagrams = script["architect"][0]["diagrams"]
    diagrams[1]["name"] = "Use-Cases"
    diagrams[2]["name"] = "类图"
    diagrams.append({**diagrams[2], "name": "时序图"})
    orch = make_orchestrator(script)
    pid = approved_requirements(orch)
    ids = [a.id for a in orch.run_action(pid, P.DESIGN, "generate", {}).outcome.artifacts]
    assert len(ids) == len(set(ids)) == 4
    assert ids[:2] == ["diagram-use-cases", "diagram-use-cases-2"]
