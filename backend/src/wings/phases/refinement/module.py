"""P3 Design refinement wing: a reviewer finds problems, an architect applies the accepted ones or a
developer's comment to the whole diagram set, and code checks consistency and coverage every time.

The wing owns the refined copy of the design (`refined-<slug>` artifacts); later wings use it when it
exists, else the design of P2 (`PhaseContext.current_design`). See ADR 0012.
"""

from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError

from wings.application.agent import LLMAgent, document_turns, turns_from
from wings.application.phase import ActionOutcome, ActionSpec, AgentInfo, PhaseContext, PhaseModule
from wings.application.ports import ChatTurn
from wings.application.registry import load_prompt
from wings.application.tools import DESIGN_TOOLS
from wings.domain.artifacts import Artifact, ArtifactKind, agent_author
from wings.domain.diagrams import DiagramItem, describe_set, unique_slugs
from wings.domain.errors import InvalidInputError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.trace import requirement_coverage
from wings.domain.uml import basic_problems, check_consistency
from wings.phases.refinement.schema import Finding, RefinerOutput, ReviewOutput

REVIEW_ID = "review"


class ReviewInput(BaseModel):
    focus: str = Field("", description="Optional: what the reviewer should look at most closely")


class ApplyInput(BaseModel):
    findings: list[str] = Field(min_length=1, description="Ids of the findings to apply, e.g. F1, F3")
    note: str = Field("", description="Optional: how to apply them")


class CommentInput(BaseModel):
    diagram: str = Field(min_length=1, description="Name of the diagram you comment on")
    comment: str = Field(min_length=1, description="What should change; the whole set is updated consistently")


class DiscussInput(BaseModel):
    question: str = Field(min_length=1, description="Ask about the review or the refined design; nothing is changed")


class RefinementPhase(PhaseModule):
    id: ClassVar[PhaseId] = PhaseId.REFINEMENT
    title: ClassVar[str] = "Design refinement"
    summary: ClassVar[str] = "A reviewer checks the design; accepted findings and your comments update all diagrams consistently."
    requires: ClassVar[list[PhaseId]] = [PhaseId.DESIGN]

    def __init__(self) -> None:
        pkg = __package__ or "wings.phases.refinement"
        self.reviewer = LLMAgent("reviewer", "Design reviewer: finds inconsistencies, gaps and unclear responsibilities", load_prompt(pkg, "reviewer.md"), tier="frontier")
        self.refiner = LLMAgent("refiner", "Architect who applies accepted findings and comments to the whole design", load_prompt(pkg, "refiner.md"), tier="frontier")
        self.explainer = LLMAgent("reviewer", "Explains the review", load_prompt(pkg, "discuss.md"), tier="mid")

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="review", label="Review design", description="Let the reviewer check the design; code checks run first.", input_model=ReviewInput, message_field="focus"),
            ActionSpec(name="apply", label="Apply findings", description="Apply the selected findings to all diagrams.", input_model=ApplyInput, message_field="note"),
            ActionSpec(name="comment", label="Comment", description="Comment on one diagram; the whole set is updated consistently.", input_model=CommentInput, message_field="comment"),
            ActionSpec(name="discuss", label="Discuss", description="Ask about the review or the refined design.", input_model=DiscussInput, message_field="question"),
        ]

    @property
    def agents(self) -> list[AgentInfo]:
        return [AgentInfo(name=a.name, role=a.role, tier=a.tier) for a in (self.reviewer, self.refiner)]

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        requirements = next((a for a in ctx.artifacts(PhaseId.REQUIREMENTS) if a.kind is ArtifactKind.REQUIREMENTS), None)
        design = ctx.current_design()
        if requirements is None or not design:
            raise InvalidTransitionError("There is no design to refine yet; finish the design phase first.")
        context = [
            ChatTurn(role="user", content=f"Approved requirements:\n{requirements.text}"),
            ChatTurn(role="user", content="Current design:\n" + describe_set([(d.content.get("kind", ""), d.title, d.text or "") for d in design])),
        ]
        docs = document_turns(ctx, PhaseId.REQUIREMENTS, PhaseId.DESIGN, ctx.phase)
        review = next((a for a in ctx.artifacts(self.id) if a.id == REVIEW_ID and not a.retired), None)

        if action == "discuss":
            extra = [ChatTurn(role="user", content=f"Current review:\n{review.text}")] if review else []
            return ActionOutcome(reply=self.explainer.chat(ctx, docs + context + extra + turns_from(ctx.messages())))
        if action == "review":
            return self._review(ctx, payload, requirements, design, docs + context)
        if action == "apply":
            if review is None:
                raise InvalidTransitionError("There is no review yet; run Review design first.")
            findings = [Finding.model_validate(f) for f in review.content.get("findings", [])]
            wanted = [i.strip().upper() for i in payload.findings]
            unknown = [i for i in wanted if i not in {f.id for f in findings}]
            if unknown:
                raise InvalidInputError(f"No finding {', '.join(unknown)} in the current review.")
            chosen = [f for f in findings if f.id in wanted]
            ask = "Apply these accepted findings:\n" + "\n".join(f"{f.id} [{f.severity}] {f.diagram}: {f.finding} Suggestion: {f.suggestion}" for f in chosen)
            if payload.note:
                ask += f"\nDeveloper's note: {payload.note}"
            outcome = self._refine(ctx, docs + context + [ChatTurn(role="user", content=ask)], requirements, design)
            marked = [f.model_copy(update={"status": "applied"}) if f.id in wanted else f for f in findings]
            outcome.artifacts.append(self._review_artifact(review.content.get("summary", ""), marked, review.content.get("reviewed", "")))
            return outcome
        if action == "comment":
            names = {d.title.lower(): d.title for d in design}
            if payload.diagram.lower() not in names:
                raise InvalidInputError(f"There is no diagram '{payload.diagram}'. Diagrams: {', '.join(d.title for d in design)}.")
            ask = f"The developer comments on the diagram '{names[payload.diagram.lower()]}':\n{payload.comment}\nUpdate every diagram this touches."
            return self._refine(ctx, docs + context + [ChatTurn(role="user", content=ask)], requirements, design)
        raise NotFoundError(action)

    # Review: code checks first, then the reviewer; both end up as numbered findings.

    def _review(self, ctx: PhaseContext, payload: Any, requirements: Artifact, design: list[Artifact], turns: list[ChatTurn]) -> ActionOutcome:
        checks = self._checks(requirements, design)
        ask = "Review this design."
        if payload.focus:
            ask += f" Focus on: {payload.focus}"
        if checks:
            ask += "\nCode checks already found these problems (they are listed as findings already, do not repeat them):\n" + "\n".join(f"- {c.finding}" for c in checks)
        out = self.reviewer.ask(ctx, turns + [ChatTurn(role="user", content=ask)], ReviewOutput, tools=DESIGN_TOOLS)
        findings = [*checks, *[f.model_copy(update={"source": "reviewer", "status": "open"}) for f in out.findings]]
        numbered = [f.model_copy(update={"id": f"F{i}"}) for i, f in enumerate(findings, start=1)]
        reviewed = "refinement" if design[0].phase is PhaseId.REFINEMENT else "design"
        artifact = self._review_artifact(out.summary, numbered, reviewed)
        high = sum(f.severity == "high" for f in numbered)
        reply = f"{len(numbered)} finding(s), {high} high. {out.summary}".strip()
        if not numbered:
            reply = f"No findings. {out.summary}".strip()
        return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=[artifact], data={"findings": len(numbered)})

    def _checks(self, requirements: Artifact, design: list[Artifact]) -> list[Finding]:
        found: list[Finding] = []
        for d in design:
            for problem in basic_problems(d.text or ""):
                found.append(Finding(severity="high", diagram=d.title, finding=problem, suggestion="Fix the PlantUML source.", source="check"))
        classes = [d for d in design if d.content.get("kind") == "class"]
        sequences = {d.title: d.text or "" for d in design if d.content.get("kind") == "sequence"}
        if classes and sequences:
            for problem in check_consistency(classes[0].text or "", sequences):
                found.append(Finding(severity="medium", diagram="all", finding=problem, suggestion="Make the class and sequence diagrams agree.", source="check"))
        report = requirement_coverage([requirements, *design])
        if report.uncovered:
            found.append(
                Finding(severity="high", diagram="all", finding=f"Not covered by any diagram: {', '.join(report.uncovered)}.", suggestion="Show these requirements in a diagram.", source="check")
            )
        return found

    # Refine: the architect returns the whole set; code checks it again.

    def _refine(self, ctx: PhaseContext, turns: list[ChatTurn], requirements: Artifact, design: list[Artifact]) -> ActionOutcome:
        out = self.refiner.ask(ctx, turns, RefinerOutput, tools=DESIGN_TOOLS)
        new = [self._diagram(d, slug) for d, slug in zip(out.diagrams, unique_slugs(out.diagrams))]
        ids = {a.id for a in new}
        current_refined = [a for a in ctx.artifacts(self.id) if a.kind is ArtifactKind.DIAGRAM and not a.retired]
        retired = [a.model_copy(update={"retired": True}) for a in current_refined if a.id not in ids]
        report = requirement_coverage([requirements, *new])
        classes = [a for a in new if a.content.get("kind") == "class"]
        sequences = {a.title: a.text or "" for a in new if a.content.get("kind") == "sequence"}
        consistency = check_consistency(classes[0].text or "", sequences) if classes and sequences else []
        reply = f"{len(new)} diagram(s) refined. {out.notes}".strip()
        if report.uncovered:
            reply += f"\nNot covered by any diagram: {', '.join(report.uncovered)}."
        if consistency:
            reply += "\nThe diagrams disagree (checked by code):\n- " + "\n- ".join(consistency)
        return ActionOutcome(
            status=PhaseStatus.DRAFT,
            reply=reply,
            artifacts=[*new, *retired],
            data={"coverage": report.model_dump() | {"ratio": report.ratio}, "consistency": consistency},
        )

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        if artifact.kind is not ArtifactKind.DIAGRAM or text is None:
            raise InvalidInputError("Edit the PlantUML source of a refined diagram; the review is changed by Review design and Apply findings.")
        try:
            item = DiagramItem(name=artifact.title, kind=artifact.content["kind"], plantuml=text, covers=artifact.covers, rationale=artifact.content.get("rationale", ""))
        except ValidationError as err:
            raise InvalidInputError(f"Invalid diagram: {err.errors(include_url=False)[0]['msg']}") from err
        return self._diagram(item, artifact.id.removeprefix("refined-")).model_copy(update={"author": artifact.author})

    def _diagram(self, d: DiagramItem, slug: str) -> Artifact:
        return Artifact(
            id=f"refined-{slug}",
            kind=ArtifactKind.DIAGRAM,
            phase=self.id,
            title=d.name,
            content={"kind": d.kind, "rationale": d.rationale},
            text=d.plantuml,
            path=f"refinement/{slug}.puml",
            covers=d.covers,
            author=agent_author(self.refiner.name),
        )

    def _review_artifact(self, summary: str, findings: list[Finding], reviewed: str) -> Artifact:
        lines = ["# Design review", "", summary, ""]
        for f in findings:
            mark = " (applied)" if f.status == "applied" else ""
            lines += [f"## {f.id} [{f.severity}] {f.diagram}{mark}", "", f.finding, "", f"Suggestion: {f.suggestion}", ""]
        return Artifact(
            id=REVIEW_ID,
            kind=ArtifactKind.REVIEW,
            phase=self.id,
            title="Design review",
            content={"summary": summary, "findings": [f.model_dump() for f in findings], "reviewed": reviewed},
            text="\n".join(lines),
            path="refinement/review.md",
            author=agent_author(self.reviewer.name),
        )
