"""P7 Maintenance wing: change requests that move through every phase, and a consistency check.

- change: the impact analyst classifies the request (bug, change, new requirement) and names the
  affected requirements; code checks the ids and computes from the trace which diagrams, files and
  tests they touch and which phases have to move. The result is a `change-<n>` artifact and a next
  action that starts the change in the right wing (requirements revise, or codegen revise for a bug).
  When the developer runs that step, the orchestrator marks every later phase stale, so the gates walk
  the developer through the update. `content.phases` only tells the developer which phases will move.
- check: computed by code only. Design versus code drift (class diagram against the Python classes)
  and how far every requirement got (diagram, code, tests, latest test result). When design and code
  drift apart, the developer picks the direction: update the design from the code, or the code from
  the design.
"""

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from wings.application.agent import LLMAgent, turns_from
from wings.application.phase import ActionOutcome, ActionSpec, AgentInfo, PhaseContext, PhaseModule
from wings.application.ports import ChatTurn
from wings.application.registry import load_prompt
from wings.application.tools import TRACE_IMPACT
from wings.domain.artifacts import Artifact, ArtifactKind, agent_author
from wings.domain.code import DriftReport, compare_design_and_code
from wings.domain.errors import InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.trace import RequirementStatus, impact, requirement_status, requirement_titles, test_results
from wings.phases.maintenance.schema import ImpactOutput

CHECK_ID = "consistency"
KIND_LABEL = {"bug": "Bug", "change": "Change", "new_requirement": "New requirement"}


class ChangeInput(BaseModel):
    request: str = Field(min_length=1, description="What should change? A bug, a change or a new requirement.")


class NoInput(BaseModel):
    pass


class DiscussInput(BaseModel):
    question: str = Field(min_length=1, description="Ask about changes or the consistency check; nothing is changed")


class MaintenancePhase(PhaseModule):
    id: ClassVar[PhaseId] = PhaseId.MAINTENANCE
    title: ClassVar[str] = "Maintenance"
    summary: ClassVar[str] = "Takes change requests and bug reports through every phase, and checks that design, code and tests still agree."
    requires: ClassVar[list[PhaseId]] = [PhaseId.DEPLOYMENT]

    def __init__(self) -> None:
        pkg = __package__ or "wings.phases.maintenance"
        self.analyst = LLMAgent("impact_analyst", "Impact analyst: classifies a change and plans it through every phase", load_prompt(pkg, "impact.md"), tier="mid")
        self.explainer = LLMAgent("impact_analyst", "Explains changes and checks", load_prompt(pkg, "discuss.md"), tier="mid")

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="change", label="Request a change", description="Describe a change, a bug or a new requirement; see what it touches.", input_model=ChangeInput, message_field="request"),
            ActionSpec(name="check", label="Check consistency", description="Compare design, code and tests; computed by code.", input_model=NoInput),
            ActionSpec(name="discuss", label="Discuss", description="Ask about a change or the check.", input_model=DiscussInput, message_field="question"),
        ]

    @property
    def agents(self) -> list[AgentInfo]:
        return [AgentInfo(name=self.analyst.name, role=self.analyst.role, tier=self.analyst.tier)]

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        if action == "change":
            assert isinstance(payload, ChangeInput)
            return self._change(ctx, payload.request)
        if action == "check":
            return self._check(ctx)
        if action == "discuss":
            mine = [a for a in ctx.artifacts(self.id) if not a.retired]
            context = [ChatTurn(role="user", content="Changes and checks so far:\n" + "\n\n".join(a.text or "" for a in mine))] if mine else []
            return ActionOutcome(reply=self.explainer.chat(ctx, context + turns_from(ctx.messages())))
        raise NotFoundError(action)

    # change ---------------------------------------------------------------------------------

    def _change(self, ctx: PhaseContext, request: str) -> ActionOutcome:
        artifacts = ctx.artifacts()
        requirements = next((a for a in artifacts if a.kind is ArtifactKind.REQUIREMENTS and not a.retired), None)
        if requirements is None:
            raise InvalidTransitionError("There are no requirements to change.")
        titles = requirement_titles(artifacts)
        turns = [
            ChatTurn(role="user", content=f"Current requirements:\n{requirements.text}"),
            ChatTurn(role="user", content=f"Change request:\n{request}"),
        ]
        out = self.analyst.ask(ctx, turns, ImpactOutput, tools=[TRACE_IMPACT])

        affected = [rid for rid in dict.fromkeys(out.affected) if rid in titles]
        unknown = [rid for rid in out.affected if rid not in titles]
        touched = impact(artifacts, affected)
        results = test_results(artifacts)
        number = 1 + len([a for a in ctx.artifacts(self.id) if a.kind is ArtifactKind.CHANGE_REQUEST])
        moves = self._phases_to_move(out)

        lines = [f"# Change {number}: {out.summary}", "", f"Request: {request}", "", f"Kind: {KIND_LABEL[out.kind]}", ""]
        if affected:
            lines.append("## Affected requirements")
            for rid in affected:
                found = ", ".join(a.title for a in touched[rid]) or "nothing traces to it yet"
                lines.append(f"- {rid} {titles[rid]}: {found}. Latest test: {results.get(rid, 'not run')}.")
            lines.append("")
        if unknown:
            lines += [f"Ignored ids that do not exist: {', '.join(unknown)}.", ""]
        if out.requirements_update:
            lines += ["## Requirements update", out.requirements_update, ""]
        if out.fix:
            lines += ["## Fix", out.fix, ""]
        lines += ["## Plan", *[f"{i}. {s}" for i, s in enumerate(out.steps, 1)]]

        artifact = Artifact(
            id=f"change-{number}",
            kind=ArtifactKind.CHANGE_REQUEST,
            phase=self.id,
            title=f"Change {number}: {out.summary}",
            content={
                "number": number,
                "request": request,
                "kind": out.kind,
                "summary": out.summary,
                "affected": affected,
                "unknown": unknown,
                "impact": {rid: [a.model_dump() for a in touched[rid]] for rid in affected},
                "phases": moves,
                "requirements_update": out.requirements_update,
                "fix": out.fix,
                "steps": out.steps,
            },
            text="\n".join(lines),
            path=f"maintenance/change-{number}.md",
            author=agent_author(self.analyst.name),
        )
        reply = f"{KIND_LABEL[out.kind]}: {out.summary}"
        if affected:
            reply += f"\nTouches {', '.join(affected)}; " + ("; ".join(f"{len(touched[r])} artifact(s) trace to {r}" for r in affected)) + "."
        reply += f"\nPhases that move: {', '.join(moves)}."
        reply += "\nStart the change with the button below. Each phase then shows what is out of date, in order."
        return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=[artifact], data={"next_actions": [self._first_step(out)], "affected": affected})

    @staticmethod
    def _phases_to_move(out: ImpactOutput) -> list[str]:
        if out.kind == "bug":
            return ["code", "tests", "deployment"]
        return ["requirements", "design", "refinement", "code", "tests", "deployment"]

    @staticmethod
    def _first_step(out: ImpactOutput) -> dict[str, Any]:
        if out.kind == "bug" and out.fix:
            return {"label": "Send the fix to Code generation", "phase": PhaseId.CODEGEN.value, "action": "revise", "input": {"feedback": out.fix}}
        update = out.requirements_update or out.summary
        return {"label": "Update the requirements", "phase": PhaseId.REQUIREMENTS.value, "action": "revise", "input": {"feedback": update}}

    # check ----------------------------------------------------------------------------------

    def _check(self, ctx: PhaseContext) -> ActionOutcome:
        artifacts = ctx.artifacts()
        code = {a.content["path"]: a.text or "" for a in artifacts if a.kind is ArtifactKind.SOURCE_FILE and not a.retired}
        if not code:
            raise InvalidTransitionError("There is no code to check yet.")
        classes = [a for a in ctx.current_design() if a.content.get("kind") == "class"]
        diagram = classes[0] if classes else None
        drift: DriftReport | None = compare_design_and_code(diagram.text or "", code) if diagram else None
        status = requirement_status(artifacts)
        hand_edited = sorted(a.content["path"] for a in artifacts if a.kind is ArtifactKind.SOURCE_FILE and not a.retired and a.author == "developer")
        stale = [ph.value for ph, st in ctx.project.phases.items() if st.status is PhaseStatus.STALE and ph is not self.id]  # this check brings P7 itself up to date

        verified = [r.id for r in status if r.verified]
        gaps = [r for r in status if not (r.design and r.code and r.tests and r.verified)]
        lines = ["# Consistency check", "", "Computed by code; no model was asked.", "", "## Design and code"]
        if drift is None:
            lines.append("There is no class diagram to compare with.")
        elif drift.in_sync:
            lines.append(f"The code implements every class and operation of '{diagram.title}', and nothing more.")
        else:
            lines += [f"- {line}" for line in drift.lines()]
        if hand_edited:
            lines.append(f"Edited by hand: {', '.join(hand_edited)}.")
        lines += ["", "## Requirements", f"{len(verified)} of {len(status)} requirements are verified by passing tests.", ""]
        lines += ["| Requirement | Design | Code | Tests | Result |", "|---|---|---|---|---|"]
        mark = {True: "yes", False: "no"}
        lines += [f"| {r.id} {r.title} | {mark[r.design]} | {mark[r.code]} | {mark[r.tests]} | {r.result or 'not run'} |" for r in status]
        if stale:
            lines += ["", f"Out of date: {', '.join(stale)}."]

        artifact = Artifact(
            id=CHECK_ID,
            kind=ArtifactKind.DRIFT_REPORT,
            phase=self.id,
            title="Consistency check",
            content={
                "diagram": diagram.title if diagram else None,
                "in_sync": drift.in_sync if drift else None,
                "drift": drift.model_dump() if drift else None,
                "drift_lines": drift.lines() if drift else [],
                "hand_edited": hand_edited,
                "requirements": [r.model_dump() | {"verified": r.verified} for r in status],
                "verified": len(verified),
                "total": len(status),
                "stale": stale,
            },
            text="\n".join(lines),
            path="reports/consistency.md",
            author="system:check",
        )

        reply_lines = []
        actions: list[dict[str, Any]] = []
        if drift is not None and not drift.in_sync:
            found = drift.lines()
            reply_lines.append("Design and code disagree:\n- " + "\n- ".join(found))
            reply_lines.append("Pick a direction: update the class diagram to match the code, or the code to match the diagram.")
            listing = "; ".join(found)
            actions = [
                {
                    "label": "Update the design from the code",
                    "phase": PhaseId.REFINEMENT.value,
                    "action": "comment",
                    "input": {"diagram": diagram.title, "comment": f"Update the diagrams to match the code: {listing}"},
                },
                {
                    "label": "Update the code from the design",
                    "phase": PhaseId.CODEGEN.value,
                    "action": "revise",
                    "input": {"feedback": f"Make the code match the class diagram: {listing}"},
                },
            ]
        elif drift is not None:
            reply_lines.append("Design and code agree.")
        reply_lines.append(f"{len(verified)} of {len(status)} requirements are verified by passing tests.")
        if gaps:
            reply_lines.append("Not there yet: " + ", ".join(f"{r.id} ({self._gap(r)})" for r in gaps[:8]) + ".")
        if stale:
            reply_lines.append(f"Out of date: {', '.join(stale)}.")
        return ActionOutcome(status=PhaseStatus.DRAFT, reply="\n".join(reply_lines), artifacts=[artifact], data={"next_actions": actions})

    @staticmethod
    def _gap(r: RequirementStatus) -> str:
        if not r.design:
            return "no diagram"
        if not r.code:
            return "no code"
        if not r.tests:
            return "no test"
        return f"test {r.result}" if r.result else "tests not run"
