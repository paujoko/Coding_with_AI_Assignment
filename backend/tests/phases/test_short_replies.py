"""Chat replies stay short: the result and the one open point. Details are in the artifacts.

The trigger was a deployer reply of about 150 words that repeated what the results panel showed.
Prompts ask for two short sentences; code holds the line with a soft cap and never refuses long text.
"""

import copy
import re
from pathlib import Path

import pytest

import wings.phases
from wings.adapters.sandbox import LocalSandbox
from wings.domain.phases import PhaseId as P

PROMPTS = sorted(Path(wings.phases.__file__).parent.glob("*/prompts/*.md"))
LONG = "This sentence only repeats what the results panel already shows to the developer. " * 15


def words(text: str) -> int:
    return len(text.split())


def lead(reply: str) -> str:
    """The prose of a reply: everything before the first computed list."""
    return reply.split("\n- ")[0]


def test_there_are_prompts_to_check():
    assert len(PROMPTS) >= 14


@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_every_prompt_asks_for_a_short_chat_text(prompt: Path):
    text = prompt.read_text(encoding="utf-8")
    assert re.search(r"at most two short sentences \(about 40 words\)|one short sentence", text), f"{prompt} does not limit the chat text"
    assert "a few clear sentences" not in text


def test_no_schema_refuses_long_text():
    """Length is trimmed by instruction and by code, never by validation: a refusal costs a model call."""
    for schema in Path(wings.phases.__file__).parent.glob("*/schema.py"):
        assert "max_length" not in schema.read_text(encoding="utf-8"), schema


def test_the_demo_replies_of_every_wing_are_short(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    orch.sandbox = LocalSandbox()
    pid = orch.create_project("Todo").id
    steps = [
        (P.REQUIREMENTS, "start", {"description": "A todo app"}),
        (P.REQUIREMENTS, "answer", {"answers": "CLI"}),
        (P.DESIGN, "generate", {}),
        (P.REFINEMENT, "review", {}),
        (P.REFINEMENT, "apply", {"findings": ["F1", "F2"]}),
        (P.CODEGEN, "generate", {}),
    ]
    approve_after = {1: P.REQUIREMENTS, 2: P.DESIGN, 4: P.REFINEMENT}
    for i, (phase, action, payload) in enumerate(steps):
        reply = orch.run_action(pid, phase, action, payload).outcome.reply
        if i != 0:  # the first reply lists the analyst's questions, one line each
            assert words(lead(reply)) <= 60, (phase, action, reply)
        else:
            assert all(words(line) <= 30 for line in reply.splitlines()), reply
        if i in approve_after:
            orch.approve(pid, approve_after[i])


def test_scripted_chat_answers_are_two_short_sentences(demo_script):
    for agent, replies in demo_script.items():
        if agent.endswith(":chat"):
            for reply in replies:
                assert words(reply) <= 45, (agent, words(reply))


def test_long_notes_are_cut_at_a_sentence_end_in_design_refinement_and_code(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    script["architect"][0]["notes"] = LONG
    script["reviewer"][0]["summary"] = LONG
    script["refiner"][0]["notes"] = LONG
    script["coder"][0]["notes"] = LONG
    orch = make_orchestrator(script)
    pid = walk(orch, P.DESIGN)
    design = orch.run_action(pid, P.DESIGN, "generate", {})
    orch.approve(pid, P.DESIGN)
    review = orch.run_action(pid, P.REFINEMENT, "review", {})
    refined = orch.run_action(pid, P.REFINEMENT, "apply", {"findings": ["F1", "F2"]})
    orch.approve(pid, P.REFINEMENT)
    code = orch.run_action(pid, P.CODEGEN, "generate", {})
    for result in (design, review, refined, code):
        prose = lead(result.outcome.reply).split("\n")[0]
        assert len(prose) <= 400 and prose.endswith("."), prose
    # Nothing is lost: the full notes travel with the message, the full summary is in the review
    # (after Apply as `review_summary`: `summary` then says what was applied).
    assert design.outcome.data["notes"] == LONG and refined.outcome.data["notes"] == LONG and code.outcome.data["notes"] == LONG
    assert review.outcome.artifacts[0].content["summary"] == LONG
    assert orch.store.get_artifact(pid, "review").content["review_summary"] == LONG


def test_the_questions_reply_names_each_question_once_without_the_reasons(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = orch.create_project("Todo").id
    asked = orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "A todo app"})
    assert "Q1. Should it run in the terminal or in the browser?" in asked.outcome.reply.splitlines()
    assert asked.outcome.data["questions"][0]["why"]  # the reason is kept as data for the cards
