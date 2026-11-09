"""P4 Code generation wing: code from the (refined) design, checked against the class diagram by code.

Each file is one artifact (`source-<slug>`, kind source_file). After every generation the design and
the code are compared with `ast` (domain/code.py); the result goes into the reply and `data.drift`.
"""

from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError

from wings.application.agent import LLMAgent, document_turns, turns_from
from wings.application.phase import ActionOutcome, ActionSpec, AgentInfo, PhaseContext, PhaseModule
from wings.application.ports import ChatTurn
from wings.application.registry import load_prompt
from wings.application.tools import CODE_TOOLS
from wings.domain.artifacts import Artifact, ArtifactKind, agent_author
from wings.domain.code import compare_design_and_code
from wings.domain.diagrams import describe_set
from wings.domain.errors import InvalidInputError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.phases.codegen.schema import CoderOutput, SourceFile, file_id


class GenerateInput(BaseModel):
    guidance: str = Field("", description="Optional: anything the developer agent should take into account")


class FeedbackInput(BaseModel):
    feedback: str = Field(min_length=1, description="What should change in the code?")


class DiscussInput(BaseModel):
    question: str = Field(min_length=1, description="Ask about the code; nothing is changed")


class CodegenPhase(PhaseModule):
    id: ClassVar[PhaseId] = PhaseId.CODEGEN
    title: ClassVar[str] = "Code generation"
    summary: ClassVar[str] = "Generates Python code from the approved design; code checks that classes and operations match the class diagram."
    requires: ClassVar[list[PhaseId]] = [PhaseId.REFINEMENT]

    def __init__(self) -> None:
        pkg = __package__ or "wings.phases.codegen"
        self.coder = LLMAgent("coder", "Developer: writes Python code that follows the design", load_prompt(pkg, "system.md"), tier="mid")
        self.explainer = LLMAgent("coder", "Explains the code", load_prompt(pkg, "discuss.md"), tier="mid")

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="generate", label="Generate code", description="Write the code from the approved design.", input_model=GenerateInput, message_field="guidance"),
            ActionSpec(name="revise", label="Revise", description="Ask for a change in the code.", input_model=FeedbackInput, message_field="feedback"),
            ActionSpec(name="discuss", label="Discuss", description="Ask about the code.", input_model=DiscussInput, message_field="question"),
        ]

    @property
    def agents(self) -> list[AgentInfo]:
        return [AgentInfo(name=self.coder.name, role=self.coder.role, tier=self.coder.tier)]

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        requirements = next((a for a in ctx.artifacts(PhaseId.REQUIREMENTS) if a.kind is ArtifactKind.REQUIREMENTS), None)
        design = ctx.current_design()
        if requirements is None or not design:
            raise InvalidTransitionError("There is no approved design yet; finish design and refinement first.")
        current = self._files(ctx)
        context = [
            ChatTurn(role="user", content=f"Approved requirements:\n{requirements.text}"),
            ChatTurn(role="user", content="Approved design:\n" + describe_set([(d.content.get("kind", ""), d.title, d.text or "") for d in design])),
        ]
        docs = document_turns(ctx, PhaseId.REQUIREMENTS, ctx.phase)
        code = [ChatTurn(role="user", content="Current code:\n" + "\n\n".join(f"### {a.content.get('path')}\n{a.text}" for a in current))] if current else []

        if action == "discuss":
            return ActionOutcome(reply=self.explainer.chat(ctx, docs + context + code + turns_from(ctx.messages())))
        if action == "generate":
            turns = context + ([ChatTurn(role="user", content=f"Guidance: {payload.guidance}")] if payload.guidance else [])
        elif action == "revise":
            if not current:
                raise InvalidTransitionError("There is no code to revise yet; use Generate code.")
            turns = context + code + turns_from(ctx.messages())
        else:
            raise NotFoundError(action)

        out = self.coder.ask(ctx, docs + turns, CoderOutput, tools=CODE_TOOLS)
        new = [self._artifact(f) for f in out.files]
        ids = {a.id for a in new}
        retired = [a.model_copy(update={"retired": True}) for a in current if a.id not in ids]
        classes = [d for d in design if d.content.get("kind") == "class"]
        drift = compare_design_and_code(classes[0].text or "", {f.path: f.content for f in out.files}) if classes else None
        reply = f"{len(new)} file(s) written. Run: {out.run}. {out.notes}".strip()
        if drift and not drift.in_sync:
            reply += "\nCode and class diagram differ (checked by code):\n- " + "\n- ".join(drift.lines())
        elif drift:
            reply += "\nChecked by code: every class and operation of the class diagram is in the code, and nothing more."
        return ActionOutcome(
            status=PhaseStatus.DRAFT,
            reply=reply,
            artifacts=[*new, *retired],
            data={"run": out.run, "drift": drift.lines() if drift else []},
        )

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        if text is None:
            raise InvalidInputError("Edit the file's text.")
        try:
            item = SourceFile(path=artifact.content["path"], purpose=artifact.content.get("purpose", ""), covers=artifact.covers, content=text)
        except ValidationError as err:
            raise InvalidInputError(f"Invalid file: {err.errors(include_url=False)[0]['msg']}") from err
        return self._artifact(item).model_copy(update={"author": artifact.author})

    def _files(self, ctx: PhaseContext) -> list[Artifact]:
        return [a for a in ctx.artifacts(self.id) if a.kind is ArtifactKind.SOURCE_FILE and not a.retired]

    def _artifact(self, f: SourceFile) -> Artifact:
        return Artifact(
            id=file_id(f.path),
            kind=ArtifactKind.SOURCE_FILE,
            phase=self.id,
            title=f.path,
            content={"path": f.path, "purpose": f.purpose, "language": "python" if f.path.endswith(".py") else "text"},
            text=f.content,
            path=f"app/{f.path}",
            covers=f.covers,
            author=agent_author(self.coder.name),
        )
