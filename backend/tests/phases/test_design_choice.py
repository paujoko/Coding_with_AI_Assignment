"""P2 Design: the developer chooses the diagram kinds and the level before the architect draws.

Real run 2026-11-25: the architect took about two minutes and nine tool calls for a design nobody had
asked to be that large. The choice is part of the generate input and is kept by revisions.
"""

import copy

import pytest

from wings.adapters.sandbox import LocalSandbox
from pydantic import ValidationError

from wings.domain.phases import PhaseId as P
from wings.phases.design.module import GenerateInput


def approved_requirements(orch) -> str:
    pid = orch.create_project("Todo").id
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "todo"})
    orch.run_action(pid, P.REQUIREMENTS, "answer", {"answers": "cli"})
    orch.approve(pid, P.REQUIREMENTS)
    return pid


def architect_requests(orch) -> list[str]:
    return ["\n".join(t.content or "" for t in c.messages) for c in orch.llm.calls if c.agent == "architect" and c.json_mode]


def only(script: dict, *kinds: str) -> dict:
    """The demo script with the architect drawing only these kinds; the class diagram covers every requirement."""
    script = copy.deepcopy(script)
    diagrams = [d for d in script["architect"][0]["diagrams"] if d["kind"] in kinds]
    for d in diagrams:
        d["covers"] = ["REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005"]
    script["architect"][0]["diagrams"] = diagrams
    script.pop("architect:tools", None)
    return script


def test_the_default_choice_is_use_case_class_and_one_sequence_at_the_simple_level():
    choice = GenerateInput()
    assert choice.kinds == ["use_case", "class", "sequence"]
    assert choice.level == "simple"
    schema = GenerateInput.model_json_schema()
    assert schema["properties"]["kinds"]["items"]["enum"][:3] == ["use_case", "class", "sequence"]
    assert schema["properties"]["level"]["enum"] == ["simple", "detailed"]


def test_an_empty_choice_is_refused(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = approved_requirements(orch)
    with pytest.raises(ValidationError):  # the API answers 422
        orch.run_action(pid, P.DESIGN, "generate", {"kinds": []})


def test_the_architect_is_told_the_chosen_kinds_and_level_and_the_diagrams_keep_the_level(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = approved_requirements(orch)
    result = orch.run_action(pid, P.DESIGN, "generate", {"kinds": ["class", "use_case"], "level": "detailed"})
    asked = architect_requests(orch)[0]
    assert "Draw exactly these diagram kinds: use case, class." in asked
    assert "Level: detailed." in asked
    assert {a.content["level"] for a in result.outcome.artifacts} == {"detailed"}


def test_a_kind_drawn_without_being_chosen_or_chosen_but_not_drawn_is_reported_by_code(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)  # the demo architect draws use case, class and sequence
    pid = approved_requirements(orch)
    result = orch.run_action(pid, P.DESIGN, "generate", {"kinds": ["use_case", "class", "activity"]})
    assert result.outcome.data["kinds"] == {"chosen": ["use_case", "class", "activity"], "missing": ["activity"], "extra": ["sequence"]}
    assert "Chosen but not drawn: activity." in result.outcome.reply
    assert "Drawn without being chosen: sequence." in result.outcome.reply


def test_a_revision_keeps_the_kinds_and_the_level_of_the_current_design(make_orchestrator, demo_script):
    orch = make_orchestrator(only(demo_script, "use_case", "class"))
    pid = approved_requirements(orch)
    orch.run_action(pid, P.DESIGN, "generate", {"kinds": ["use_case", "class"], "level": "simple"})
    orch.run_action(pid, P.DESIGN, "revise", {"feedback": "Rename Cli to CommandLine"})
    asked = architect_requests(orch)[-1]
    assert "Keep these diagram kinds: use case, class. Level: simple." in asked
    assert {a.content["level"] for a in orch.store.list_artifacts(pid, P.DESIGN) if not a.retired} == {"simple"}


def test_simple_level_allows_fewer_tool_rounds_than_detailed(make_orchestrator, demo_script):
    script = copy.deepcopy(demo_script)
    round_ = script["architect:tools"][0]
    script["architect:tools"] = [round_] * 4  # a model that would keep checking
    for level, rounds in (("simple", 2), ("detailed", 4)):
        orch = make_orchestrator(script)
        pid = approved_requirements(orch)
        orch.llm.calls.clear()
        orch.run_action(pid, P.DESIGN, "generate", {"level": level})
        calls = [c for c in orch.llm.calls if c.agent == "architect"]
        assert len(calls) == rounds + 1, level


def test_a_design_without_a_sequence_diagram_goes_through_review_code_and_tests(make_orchestrator, demo_script):
    orch = make_orchestrator(only(demo_script, "use_case", "class"))
    orch.sandbox = LocalSandbox()
    pid = approved_requirements(orch)
    result = orch.run_action(pid, P.DESIGN, "generate", {"kinds": ["use_case", "class"]})
    assert result.outcome.data["consistency"] == [] and result.outcome.data["kinds"]["missing"] == []
    orch.approve(pid, P.DESIGN)
    orch.run_action(pid, P.REFINEMENT, "review", {})
    orch.approve(pid, P.REFINEMENT)
    code = orch.run_action(pid, P.CODEGEN, "generate", {})
    assert "Checked by code" in code.outcome.reply or "differ" in code.outcome.reply  # compared with the class diagram
    orch.approve(pid, P.CODEGEN)
    orch.run_action(pid, P.TESTING, "generate", {})
    orch.run_action(pid, P.TESTING, "run", {})
    assert orch.store.get_artifact(pid, "test-report").content["green"]


def test_a_design_without_a_class_diagram_goes_through_review_and_code(make_orchestrator, demo_script):
    orch = make_orchestrator(only(demo_script, "use_case", "sequence"))
    pid = approved_requirements(orch)
    orch.run_action(pid, P.DESIGN, "generate", {"kinds": ["use_case", "sequence"]})
    orch.approve(pid, P.DESIGN)
    orch.run_action(pid, P.REFINEMENT, "review", {})
    orch.approve(pid, P.REFINEMENT)
    code = orch.run_action(pid, P.CODEGEN, "generate", {})
    assert code.outcome.data["drift"] == []  # nothing to compare with, nothing invented
    check = orch.design_check(pid)
    assert check is None or not check.checked


def test_the_reviewer_is_told_not_to_ask_for_kinds_the_developer_left_out(make_orchestrator, demo_script):
    orch = make_orchestrator(only(demo_script, "use_case", "class"))
    pid = approved_requirements(orch)
    orch.run_action(pid, P.DESIGN, "generate", {"kinds": ["use_case", "class"], "level": "simple"})
    orch.approve(pid, P.DESIGN)
    orch.run_action(pid, P.REFINEMENT, "review", {})
    asked = "\n".join(t.content or "" for t in next(c for c in orch.llm.calls if c.agent == "reviewer").messages)
    assert "The developer chose these diagram kinds: use case, class, at the simple level." in asked
