"""P3 Design refinement through the orchestrator with the scripted mock."""

import copy

import pytest

from wings.domain.errors import InvalidInputError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S


def designed(orch):
    pid = orch.create_project("Todo").id
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "A todo app"})
    orch.run_action(pid, P.REQUIREMENTS, "answer", {"answers": "CLI"})
    orch.approve(pid, P.REQUIREMENTS)
    orch.run_action(pid, P.DESIGN, "generate", {})
    orch.approve(pid, P.DESIGN)
    return pid


def test_review_numbers_findings_and_uses_tools(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = designed(orch)
    result = orch.run_action(pid, P.REFINEMENT, "review", {})
    review = result.outcome.artifacts[0]
    assert result.project.status(P.REFINEMENT) is S.DRAFT
    assert [f["id"] for f in review.content["findings"]] == ["F1", "F2", "F3"]
    assert review.content["reviewed"] == "design"
    assert any(e.kind == "agent.tool_call" and e.data["agent"] == "reviewer" for e in orch.store.list_events(pid))


def test_apply_refines_the_whole_set_and_marks_findings(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = designed(orch)
    orch.run_action(pid, P.REFINEMENT, "review", {})
    result = orch.run_action(pid, P.REFINEMENT, "apply", {"findings": ["f1", "F2"], "note": "Apply F1 and F2"})
    refined = [a for a in orch.store.list_artifacts(pid, P.REFINEMENT) if a.kind.value == "diagram"]
    assert {a.id for a in refined} == {"refined-use-cases", "refined-domain-classes", "refined-complete-a-task", "refined-runtime-parts"}
    assert "next_number" in next(a for a in refined if a.id == "refined-domain-classes").text
    assert result.outcome.data["consistency"] == []
    review = orch.store.get_artifact(pid, "review")
    assert [f["status"] for f in review.content["findings"]] == ["applied", "applied", "open"]


def test_unknown_findings_and_diagrams_are_refused(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = designed(orch)
    orch.run_action(pid, P.REFINEMENT, "review", {})
    with pytest.raises(InvalidInputError, match="F9"):
        orch.run_action(pid, P.REFINEMENT, "apply", {"findings": ["F9"]})
    with pytest.raises(InvalidInputError, match="Domain classes"):
        orch.run_action(pid, P.REFINEMENT, "comment", {"diagram": "Nope", "comment": "x"})


def test_comment_on_one_diagram_updates_the_set(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = designed(orch)
    result = orch.run_action(pid, P.REFINEMENT, "comment", {"diagram": "domain classes", "comment": "Who hands out numbers?"})
    assert len([a for a in result.outcome.artifacts if a.kind.value == "diagram"]) == 4


def test_code_checks_become_findings_before_the_reviewer_speaks(make_orchestrator, demo_script):
    script = copy.deepcopy(demo_script)
    seq = next(d for d in script["architect"][0]["diagrams"] if d["kind"] == "sequence")
    seq["plantuml"] = seq["plantuml"].replace("complete(1)", "finish(1)")
    orch = make_orchestrator(script)
    pid = designed(orch)
    review = orch.run_action(pid, P.REFINEMENT, "review", {}).outcome.artifacts[0]
    first = review.content["findings"][0]
    assert first["source"] == "check" and "finish" in first["finding"] and first["id"] == "F1"


def test_later_phases_see_the_refined_design(make_orchestrator, demo_script):
    from wings.application.phase import PhaseContext
    from wings.application.ports import ReadOnlyStore

    orch = make_orchestrator(demo_script)
    pid = designed(orch)
    ctx = PhaseContext(project=orch.project(pid), phase=P.CODEGEN, store=ReadOnlyStore(orch.store), llm=orch.llm, renderer=orch.renderer)
    assert {a.phase for a in ctx.current_design()} == {P.DESIGN}
    orch.run_action(pid, P.REFINEMENT, "review", {})
    orch.run_action(pid, P.REFINEMENT, "apply", {"findings": ["F1"]})
    assert {a.phase for a in ctx.current_design()} == {P.REFINEMENT}
