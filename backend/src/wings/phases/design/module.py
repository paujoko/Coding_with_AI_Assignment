"""P2 Design wing: approved requirements -> a consistent set of UML diagrams (PlantUML)."""

from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError

from wings.application.agent import LLMAgent, document_turns, turns_from
from wings.application.tools import DESIGN_TOOLS
from wings.application.phase import ActionOutcome, ActionSpec, AgentInfo, PhaseContext, PhaseModule
from wings.application.ports import ChatTurn
from wings.application.registry import load_prompt
from wings.domain.artifacts import Artifact, ArtifactKind, agent_author
from wings.domain.errors import InvalidInputError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.diagrams import DEFAULT_KINDS, DesignLevel, design_choice, kind_label, kind_mismatch
from wings.domain.diagrams import unique_slugs as _unique_slugs
from wings.domain.text import brief, short_list
from wings.domain.uml import check_consistency
from wings.domain.trace import requirement_coverage
from wings.phases.design.schema import ArchitectOutput, DiagramItem, DiagramKind

# Tool rounds the architect may spend on checks before it has to answer. Each round is a full model call
# (real run 2026-11-25: five calls, about two minutes); a simple design needs one round of checks.
TOOL_ROUNDS: dict[str, int] = {"simple": 2, "detailed": 4}


class GenerateInput(BaseModel):
    kinds: list[DiagramKind] = Field(
        default=list(DEFAULT_KINDS),  # in the JSON schema, so the form ticks them; pydantic copies it per instance
        min_length=1,
        description="Diagrams to draw",
        json_schema_extra={
            "option_hints": {
                "use_case": "Who uses the program for what",
                "class": "The parts of the program; the code is checked against it",
                "sequence": "The main flow, step by step",
                "activity": "A process with decisions",
                "state": "The lifecycle of one thing",
                "component": "The runtime parts and how they talk",
                "deployment": "Where each part runs",
            }
        },
    )
    level: DesignLevel = Field(
        "simple",
        description="How detailed",
        json_schema_extra={
            "option_hints": {
                "simple": "Key classes only, one sequence for the main flow. Fast.",
                "detailed": "Every class and the important scenarios. Takes longer.",
            }
        },
    )
    guidance: str = Field("", description="Optional: anything the architect should take into account")


def _choice_text(kinds: list[str], level: str) -> str:
    return ", ".join(kind_label(k) for k in kinds) + f". Level: {level}."


def chosen(payload: Any, artifacts: list[Artifact]) -> str:
    """The developer's choice as a line in the conversation (ADR 0022): "Draw: Use case, Class · simple"."""
    kinds, _ = design_choice([(k, None) for k in payload.kinds])
    return "Draw: " + ", ".join(kind_label(k) for k in kinds) + f" · {payload.level}"


class FeedbackInput(BaseModel):
    feedback: str = Field(min_length=1, description="What should change in the design?")


class DiscussInput(BaseModel):
    question: str = Field(min_length=1, description="Ask why a design choice was made; nothing is changed")


class DesignPhase(PhaseModule):
    id: ClassVar[PhaseId] = PhaseId.DESIGN
    title: ClassVar[str] = "Design"
    summary: ClassVar[str] = "Produces the UML diagrams you choose (use case, class, sequence, ...) from the approved requirements, simple or detailed."
    requires: ClassVar[list[PhaseId]] = [PhaseId.REQUIREMENTS]

    def __init__(self) -> None:
        pkg = __package__ or "wings.phases.design"
        self.architect = LLMAgent("architect", "Software architect: writes the UML design", load_prompt(pkg, "system.md"), tier="frontier")
        self.explainer = LLMAgent("architect", "Explains design choices", load_prompt(pkg, "discuss.md"), tier="frontier")

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="generate", label="Generate design", description="Create the diagrams from the approved requirements.", input_model=GenerateInput, message_field="guidance", decision=chosen),
            ActionSpec(name="revise", label="Revise", description="Ask for a change; all diagrams are updated together.", input_model=FeedbackInput, message_field="feedback"),
            ActionSpec(name="discuss", label="Discuss", description="Ask why the design looks like this.", input_model=DiscussInput, message_field="question"),
        ]

    @property
    def agents(self) -> list[AgentInfo]:
        return [AgentInfo(name=self.architect.name, role=self.architect.role, tier=self.architect.tier)]

    def approval_problem(self, artifacts: list[Artifact]) -> str | None:
        """Every functional requirement must appear in at least one diagram before the design is approved
        (checked by code; real run s03: a design covering 1 of 11 requirements could be approved)."""
        live = [a for a in artifacts if not a.retired]
        requirements = next((a for a in live if a.kind is ArtifactKind.REQUIREMENTS), None)
        diagrams = [a for a in live if a.phase is self.id and a.kind is ArtifactKind.DIAGRAM]
        if requirements is None or not diagrams:
            return None  # the general rule (a result must exist) applies
        functional = [r["id"] for r in requirements.content.get("requirements", []) if r.get("type", "functional") == "functional" and r.get("id")]
        covered = {rid for d in diagrams for rid in d.covers}
        missing = [rid for rid in functional if rid not in covered]
        if missing:
            return (
                f"No diagram covers {', '.join(missing)}. Revise the design so every functional requirement appears "
                "in at least one diagram, then accept it."
            )
        return None

    def refresh_step(self, reason: str, artifacts: list[Artifact]) -> list[tuple[str, dict[str, Any]]]:
        """Revise the diagrams that exist (the architect sees them and the new requirements); generate if there are none."""
        if any(a.phase is self.id and a.kind is ArtifactKind.DIAGRAM and not a.retired for a in artifacts):
            return [("revise", {"feedback": f"The requirements changed. Update every diagram this touches and keep the rest as it is.\n{reason}"})]
        return [("generate", {"guidance": reason})]

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        requirements = next((a for a in ctx.artifacts(PhaseId.REQUIREMENTS) if a.kind is ArtifactKind.REQUIREMENTS), None)
        if requirements is None:
            raise InvalidTransitionError("No requirements found; finish the requirements phase first.")
        current = self._diagrams(ctx)
        # The architect also reads what the developer attached while the requirements were written.
        context = ChatTurn(role="user", content=f"Approved requirements:\n{requirements.text}")
        docs = document_turns(ctx, PhaseId.REQUIREMENTS, ctx.phase)

        if action == "discuss":
            design = "\n\n".join(f"{d.title}:\n{d.text}" for d in current) or "(no diagrams yet)"
            turns = [context, ChatTurn(role="user", content=f"Current design:\n{design}"), *turns_from(ctx.messages())]
            return ActionOutcome(reply=self.explainer.chat(ctx, docs + turns))
        if action == "generate":
            kinds, _ = design_choice([(k, None) for k in payload.kinds])  # reading order, no repeats
            level = payload.level
            choice = ChatTurn(role="user", content=f"The developer's choice. Draw exactly these diagram kinds: {_choice_text(kinds, level)}")
            turns = [context, choice] + ([ChatTurn(role="user", content=f"Guidance: {payload.guidance}")] if payload.guidance else [])
        elif action == "revise":
            if not current:
                raise InvalidTransitionError("There is no design to revise yet; use generate.")
            kinds, level = design_choice([(d.content.get("kind", ""), d.content.get("level")) for d in current])
            design = "\n\n".join(f"[{d.content.get('kind')}] {d.title}:\n{d.text}" for d in current)
            keep = ChatTurn(role="user", content=f"Keep these diagram kinds: {_choice_text(kinds, level)} Change them only if the developer asks for it.")
            turns = [context, ChatTurn(role="user", content=f"Current design:\n{design}"), keep, *turns_from(ctx.messages())]
        else:
            raise NotFoundError(action)

        # The architect may check its diagrams with deterministic tools before it answers.
        out = self.architect.ask(ctx, docs + turns, ArchitectOutput, tools=DESIGN_TOOLS, max_tool_rounds=TOOL_ROUNDS[level])
        new = [self._artifact(d, slug, level) for d, slug in zip(out.diagrams, _unique_slugs(out.diagrams))]
        new_ids = {a.id for a in new}
        retired = [a.model_copy(update={"retired": True}) for a in current if a.id not in new_ids]
        report = requirement_coverage([requirements, *new])
        # Checked again by code, whatever the model did with its tools.
        classes = [a for a in new if a.content.get("kind") == "class"]
        sequences = {a.title: a.text or "" for a in new if a.content.get("kind") == "sequence"}
        consistency = check_consistency(classes[0].text or "", sequences) if classes and sequences else []
        reply = f"{len(new)} diagram{'' if len(new) == 1 else 's'} ready. {brief(out.notes)}".strip()  # details are in the diagrams
        data: dict[str, Any] = {"coverage": report.model_dump() | {"ratio": report.ratio}, "consistency": consistency, "notes": out.notes}
        if action == "generate":
            # Whether the architect kept to the developer's choice is checked by code, not taken on trust.
            missing, extra = kind_mismatch(kinds, [d.kind for d in out.diagrams])
            data["kinds"] = {"chosen": kinds, "missing": missing, "extra": extra}
            if missing:
                reply += f"\nChosen but not drawn: {', '.join(kind_label(k) for k in missing)}."
            if extra:
                reply += f"\nDrawn without being chosen: {', '.join(kind_label(k) for k in extra)}."
        if report.uncovered:
            reply += f"\nNot covered by any diagram: {', '.join(report.uncovered)}."
        if consistency:
            reply += "\nThe diagrams disagree (checked by code):\n- " + "\n- ".join(short_list(consistency, "all in the review"))
        return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=new + retired, data=data)

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        if text is None:
            raise InvalidInputError("Edit the PlantUML source of the diagram.")
        try:
            item = DiagramItem(name=artifact.title, kind=artifact.content["kind"], plantuml=text, covers=artifact.covers, rationale=artifact.content.get("rationale", ""))
        except ValidationError as err:
            raise InvalidInputError(f"Invalid diagram: {err.errors(include_url=False)[0]['msg']}") from err
        return self._artifact(item, artifact.id.removeprefix("diagram-"), artifact.content.get("level"))

    def _diagrams(self, ctx: PhaseContext) -> list[Artifact]:
        return [a for a in ctx.artifacts(self.id) if a.kind is ArtifactKind.DIAGRAM and not a.retired]

    def _artifact(self, d: DiagramItem, slug: str, level: str | None) -> Artifact:
        content: dict[str, Any] = {"kind": d.kind, "rationale": d.rationale}
        if level:
            content["level"] = level  # a revision keeps the level the design was drawn with
        return Artifact(
            id=f"diagram-{slug}",
            kind=ArtifactKind.DIAGRAM,
            phase=self.id,
            title=d.name,
            content=content,
            text=d.plantuml,
            path=f"design/{slug}.puml",
            covers=d.covers,
            author=agent_author(self.architect.name),
        )
