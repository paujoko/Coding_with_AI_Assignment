"""P1 Requirements wing: vague description -> clarifying questions -> structured requirements."""

import json
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError

from wings.application.agent import LLMAgent, turns_from
from wings.application.phase import ActionOutcome, ActionSpec, AgentInfo, PhaseContext, PhaseModule
from wings.application.ports import ChatTurn
from wings.application.registry import load_prompt
from wings.domain.artifacts import Artifact, ArtifactKind, agent_author
from wings.domain.errors import InvalidInputError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.phases.requirements.schema import AnalystOutput, Question, RequirementsDoc, assign_ids, render_markdown

ARTIFACT_ID = "requirements"


class StartInput(BaseModel):
    description: str = Field(min_length=1, description="What should the software do? Rough is fine.")


class AnswerInput(BaseModel):
    answers: str = Field(min_length=1, description="Answers to the open questions")


class FeedbackInput(BaseModel):
    feedback: str = Field(min_length=1, description="What should change?")


class DiscussInput(BaseModel):
    question: str = Field(min_length=1, description="Ask about the requirements; nothing is changed")


class RequirementsPhase(PhaseModule):
    id: ClassVar[PhaseId] = PhaseId.REQUIREMENTS
    title: ClassVar[str] = "Requirements"
    summary: ClassVar[str] = "Turns a vague description into structured, testable requirements; asks instead of guessing."
    requires: ClassVar[list[PhaseId]] = []

    def __init__(self) -> None:
        pkg = __package__ or "wings.phases.requirements"
        self.analyst = LLMAgent("analyst", "Requirements analyst: asks clarifying questions, writes requirements", load_prompt(pkg, "system.md"))
        self.explainer = LLMAgent("analyst", "Answers questions about the requirements", load_prompt(pkg, "discuss.md"))

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="start", label="Start", description="Describe the software you want.", input_model=StartInput, message_field="description"),
            ActionSpec(name="answer", label="Answer", description="Answer the open questions.", input_model=AnswerInput, message_field="answers"),
            ActionSpec(name="revise", label="Revise", description="Ask for changes to the requirements.", input_model=FeedbackInput, message_field="feedback"),
            ActionSpec(name="discuss", label="Discuss", description="Ask why something is the way it is.", input_model=DiscussInput, message_field="question"),
        ]

    @property
    def agents(self) -> list[AgentInfo]:
        return [AgentInfo(name=self.analyst.name, role=self.analyst.role, tier=self.analyst.tier)]

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        current = self._current(ctx)
        if action == "discuss":
            turns = turns_from(ctx.messages())
            if current:
                turns.insert(0, ChatTurn(role="user", content=f"Current requirements:\n{current.text}"))
            return ActionOutcome(reply=self.explainer.chat(ctx, turns))
        if action == "start":
            turns = [ChatTurn(role="user", content=payload.description)]  # a fresh start ignores earlier talk
        elif action == "answer":
            turns = turns_from(ctx.messages())
        elif action == "revise":
            if current is None:
                raise InvalidTransitionError("There are no requirements to revise yet; use start.")
            turns = turns_from(ctx.messages()) + [
                ChatTurn(role="user", content="Current requirements (JSON, keep ids of requirements you keep):\n" + json.dumps(current.content)),
            ]
        else:
            raise NotFoundError(action)
        # A fresh start keeps no old ids; numbering still continues after every id ever issued.
        keep = [] if action == "start" or current is None else current.defines
        return self._outcome(self.analyst.ask(ctx, turns, AnalystOutput), keep, _issued(current))

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        if content is None:
            raise InvalidInputError("Edit the structured requirements; requirements.md is generated from them.")
        try:
            doc = RequirementsDoc.model_validate(content)
        except ValidationError as err:
            raise InvalidInputError(f"Invalid requirements: {err}") from err
        return self._artifact(doc, keep=artifact.defines, issued=_issued(artifact), author=artifact.author)

    # Helpers

    def _current(self, ctx: PhaseContext) -> Artifact | None:
        return next((a for a in ctx.artifacts(self.id) if a.id == ARTIFACT_ID), None)

    def _outcome(self, out: AnalystOutput, keep: list[str], issued: list[str]) -> ActionOutcome:
        if out.questions and not out.requirements:
            return ActionOutcome(
                status=PhaseStatus.NEEDS_INPUT,
                reply=_questions_text(out.summary, out.questions),
                data={"questions": [q.model_dump() for q in out.questions]},
            )
        if not out.requirements:
            return ActionOutcome(reply=out.summary or "The analyst returned no requirements and no questions.")
        doc = RequirementsDoc(summary=out.summary, requirements=out.requirements, assumptions=out.assumptions)
        artifact = self._artifact(doc, keep=keep, issued=issued, author=agent_author(self.analyst.name))
        reply = f"{len(artifact.defines)} requirements drafted. Review, edit or approve them."
        if out.assumptions:
            reply += f" I assumed {len(out.assumptions)} thing(s); they are listed at the end."
        return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=[artifact])

    def _artifact(self, doc: RequirementsDoc, keep: list[str], issued: list[str], author: str) -> Artifact:
        doc = doc.model_copy(update={"requirements": assign_ids(doc.requirements, keep, issued)})
        ids = [r.id for r in doc.requirements]
        return Artifact(
            id=ARTIFACT_ID,
            kind=ArtifactKind.REQUIREMENTS,
            phase=self.id,
            title="Requirements",
            content=doc.model_dump() | {"issued_ids": sorted(set(issued) | set(ids))},
            text=render_markdown(doc),
            path="requirements.md",
            defines=[r.id for r in doc.requirements],
            author=author,
        )


def _issued(artifact: Artifact | None) -> list[str]:
    """Every requirement id ever handed out in this project (kept in the artifact content)."""
    if artifact is None:
        return []
    return list(artifact.content.get("issued_ids", artifact.defines))


def _questions_text(summary: str, questions: list[Question]) -> str:
    lines = [summary, "", "Before I write requirements I need to know:"] if summary else ["I need to know:"]
    lines += [f"{q.id}. {q.question} ({q.why})" for q in questions]
    return "\n".join(lines)
