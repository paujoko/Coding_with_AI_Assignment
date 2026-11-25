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
from wings.domain.diagrams import DiagramItem, describe_set, design_choice, kind_label, unique_slugs
from wings.domain.errors import InvalidInputError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.text import brief, short_list
from wings.domain.trace import current_design, requirement_coverage
from wings.domain.uml import basic_problems, check_consistency
from wings.phases.refinement.schema import Finding, RefinerOutput, ReviewOutput

REVIEW_ID = "review"


def after_apply(applied: list[str], solved: int, still_open: int) -> str:
    """The review's summary after Apply, computed from the findings: what was applied, what code found solved,
    what is still open. The reviewer's own summary described the design before applying."""
    ids = applied[0] if len(applied) == 1 else f"{', '.join(applied[:-1])} and {applied[-1]}"
    text = f"Applied {ids} to the design."
    if solved:
        text += f" {solved} {'finding' if solved == 1 else 'findings'} found by code {'is' if solved == 1 else 'are'} solved by the refined diagrams."
    if still_open:
        text += f" {still_open} {'finding is' if still_open == 1 else 'findings are'} still open."
    else:
        text += " No finding is open."
    return text


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

    def refresh_step(self, reason: str, artifacts: list[Artifact]) -> list[tuple[str, dict[str, Any]]]:
        """A comment on the class diagram (or the first diagram) of the current design: the refiner then
        updates the whole set. It is told which findings earlier reviews applied, so they are not lost
        when the refined copy is rebuilt from a changed design."""
        design = current_design([a for a in artifacts if a.phase in (PhaseId.DESIGN, self.id)])
        if not design:
            return []
        target = next((d for d in design if d.content.get("kind") == "class"), design[0])
        review = next((a for a in artifacts if a.id == REVIEW_ID and not a.retired), None)
        applied = [f for f in (review.content.get("findings", []) if review else []) if f.get("status") == "applied"]
        comment = f"The design changed upstream. Bring the refined design up to date and keep all diagrams consistent.\n{reason}"
        if applied:
            comment += "\nKeep what earlier reviews already changed:\n" + "\n".join(f"- {f.get('id')}: {f.get('suggestion') or f.get('finding')}" for f in applied)
        return [("comment", {"diagram": target.title, "comment": comment})]

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
            # Code checks are facts about the diagrams: an open one the refined set no longer has is solved, not open.
            refined = [a for a in outcome.artifacts if a.kind is ArtifactKind.DIAGRAM and not a.retired]
            still = {c.finding for c in self._checks(requirements, refined)}
            kept = [f for f in marked if f.source != "check" or f.status == "applied" or f.finding in still]
            # The reviewer's summary described the design before applying; the review now says what changed (seen 2026-11-25).
            said = review.content.get("review_summary") or review.content.get("summary", "")
            summary = after_apply([f.id for f in chosen], solved=len(marked) - len(kept), still_open=sum(f.status == "open" for f in kept))
            outcome.artifacts.append(self._review_artifact(summary, kept, review.content.get("reviewed", ""), review_summary=said))
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
        kinds, level = design_choice([(d.content.get("kind", ""), d.content.get("level")) for d in design])
        ask = (
            f"Review this design. The developer chose these diagram kinds: {', '.join(kind_label(k) for k in kinds)}, at the {level} level. "
            "Do not ask for other kinds or for more detail than that level; judge what is there."
        )
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
        reply = f"{len(numbered)} finding{'' if len(numbered) == 1 else 's'}, {high} high. {brief(out.summary)}".strip()  # the findings are in the review
        if not numbered:
            reply = f"No findings. {brief(out.summary)}".strip()
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
        _, level = design_choice([(d.content.get("kind", ""), d.content.get("level")) for d in design])
        out = self.refiner.ask(ctx, turns, RefinerOutput, tools=DESIGN_TOOLS)
        new = [self._diagram(d, slug, level) for d, slug in zip(out.diagrams, unique_slugs(out.diagrams))]
        ids = {a.id for a in new}
        current_refined = [a for a in ctx.artifacts(self.id) if a.kind is ArtifactKind.DIAGRAM and not a.retired]
        retired = [a.model_copy(update={"retired": True}) for a in current_refined if a.id not in ids]
        report = requirement_coverage([requirements, *new])
        classes = [a for a in new if a.content.get("kind") == "class"]
        sequences = {a.title: a.text or "" for a in new if a.content.get("kind") == "sequence"}
        consistency = check_consistency(classes[0].text or "", sequences) if classes and sequences else []
        reply = f"{len(new)} diagram{'' if len(new) == 1 else 's'} refined. {brief(out.notes)}".strip()
        if report.uncovered:
            reply += f"\nNot covered by any diagram: {', '.join(report.uncovered)}."
        if consistency:
            reply += "\nThe diagrams disagree (checked by code):\n- " + "\n- ".join(short_list(consistency, "all in the next review"))
        return ActionOutcome(
            status=PhaseStatus.DRAFT,
            reply=reply,
            artifacts=[*new, *retired],
            data={"coverage": report.model_dump() | {"ratio": report.ratio}, "consistency": consistency, "notes": out.notes},
        )

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        if artifact.kind is not ArtifactKind.DIAGRAM or text is None:
            raise InvalidInputError("Edit the PlantUML source of a refined diagram; the review is changed by Review design and Apply findings.")
        try:
            item = DiagramItem(name=artifact.title, kind=artifact.content["kind"], plantuml=text, covers=artifact.covers, rationale=artifact.content.get("rationale", ""))
        except ValidationError as err:
            raise InvalidInputError(f"Invalid diagram: {err.errors(include_url=False)[0]['msg']}") from err
        return self._diagram(item, artifact.id.removeprefix("refined-"), artifact.content.get("level")).model_copy(update={"author": artifact.author})

    def _diagram(self, d: DiagramItem, slug: str, level: str | None) -> Artifact:
        content: dict[str, Any] = {"kind": d.kind, "rationale": d.rationale}
        if level:
            content["level"] = level  # the level the developer chose in Design travels with the refined copy
        return Artifact(
            id=f"refined-{slug}",
            kind=ArtifactKind.DIAGRAM,
            phase=self.id,
            title=d.name,
            content=content,
            text=d.plantuml,
            path=f"refinement/{slug}.puml",
            covers=d.covers,
            author=agent_author(self.refiner.name),
        )

    def _review_artifact(self, summary: str, findings: list[Finding], reviewed: str, review_summary: str | None = None) -> Artifact:
        lines = ["# Design review", "", summary, ""]
        if review_summary:
            lines += [f"The reviewer's summary before applying: {review_summary}", ""]
        content: dict[str, Any] = {"summary": summary, "findings": [f.model_dump() for f in findings], "reviewed": reviewed}
        if review_summary:
            content["review_summary"] = review_summary
        for f in findings:
            mark = " (applied)" if f.status == "applied" else ""
            lines += [f"## {f.id} [{f.severity}] {f.diagram}{mark}", "", f.finding, "", f"Suggestion: {f.suggestion}", ""]
        return Artifact(
            id=REVIEW_ID,
            kind=ArtifactKind.REVIEW,
            phase=self.id,
            title="Design review",
            content=content,
            text="\n".join(lines),
            path="refinement/review.md",
            author=agent_author(self.reviewer.name),
        )
