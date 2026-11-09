"""P6 Deployment wing: Dockerfile, start scripts and run notes, checked by code and by a real smoke run.

- generate and revise: the deployer writes the files (`deploy-<slug>`, kind deployment_file) and the
  check runs at once.
- check: static checks (domain/deploy.py) and the smoke command in the Sandbox with the code; the
  `deployment-check` artifact records the result. Docker itself is not run (see ADR 0013).
"""

import shlex
from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError

from wings.application.agent import LLMAgent, turns_from
from wings.application.phase import ActionOutcome, ActionSpec, AgentInfo, PhaseContext, PhaseModule
from wings.application.ports import ChatTurn
from wings.application.registry import load_prompt
from wings.domain.artifacts import Artifact, ArtifactKind, agent_author
from wings.domain.deploy import check_deployment
from wings.domain.diagrams import describe_set
from wings.domain.errors import InvalidInputError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.trace import fresh_report
from wings.phases.deployment.schema import DeployerOutput, DeployFile, deploy_id

CHECK_ID = "deployment-check"
SMOKE_TIMEOUT = 30.0


class GenerateInput(BaseModel):
    guidance: str = Field("", description="Optional: where or how it should run")


class FeedbackInput(BaseModel):
    feedback: str = Field(min_length=1, description="What should change in the deployment?")


class NoInput(BaseModel):
    pass


class DiscussInput(BaseModel):
    question: str = Field(min_length=1, description="Ask about the deployment; nothing is changed")


class DeploymentPhase(PhaseModule):
    id: ClassVar[PhaseId] = PhaseId.DEPLOYMENT
    title: ClassVar[str] = "Deployment"
    summary: ClassVar[str] = "Writes a Dockerfile and start scripts, then checks them and starts the program for real."
    requires: ClassVar[list[PhaseId]] = [PhaseId.TESTING]

    def __init__(self) -> None:
        pkg = __package__ or "wings.phases.deployment"
        self.deployer = LLMAgent("deployer", "Deployment engineer: Dockerfile, start scripts, run notes", load_prompt(pkg, "system.md"), tier="mid")
        self.explainer = LLMAgent("deployer", "Explains the deployment", load_prompt(pkg, "discuss.md"), tier="mid")

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="generate", label="Prepare deployment", description="Write the deployment files and check them.", input_model=GenerateInput, message_field="guidance"),
            ActionSpec(name="check", label="Check again", description="Run the checks and the smoke command again.", input_model=NoInput),
            ActionSpec(name="revise", label="Revise", description="Ask for a change in the deployment.", input_model=FeedbackInput, message_field="feedback"),
            ActionSpec(name="discuss", label="Discuss", description="Ask about the deployment.", input_model=DiscussInput, message_field="question"),
        ]

    @property
    def agents(self) -> list[AgentInfo]:
        return [AgentInfo(name=self.deployer.name, role=self.deployer.role, tier=self.deployer.tier)]

    def approval_problem(self, artifacts: list[Artifact]) -> str | None:
        """The deployment is approved only when its last check passed on the current files and code."""
        report = fresh_report(artifacts, ArtifactKind.DEPLOYMENT_CHECK, (ArtifactKind.DEPLOYMENT_FILE, ArtifactKind.SOURCE_FILE))
        if report is None:
            return "Check the deployment again before approving: files or code changed since the last check."
        if not report.content.get("passed"):
            return "The deployment check did not pass. Revise the files and check again before approving."
        return None

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        code = [a for a in ctx.artifacts(PhaseId.CODEGEN) if a.kind is ArtifactKind.SOURCE_FILE and not a.retired]
        if not code:
            raise InvalidTransitionError("There is no code to deploy yet.")
        current = self._files(ctx)
        check = next((a for a in ctx.artifacts(self.id) if a.id == CHECK_ID and not a.retired), None)
        listing = ChatTurn(role="user", content="Code:\n" + "\n\n".join(f"### {a.content.get('path')}\n{a.text}" for a in code))
        design = ctx.current_design()
        views = [d for d in design if d.content.get("kind") in ("component", "deployment")]
        context = [listing] + ([ChatTurn(role="user", content="Runtime views:\n" + describe_set([(d.content.get("kind", ""), d.title, d.text or "") for d in views]))] if views else [])

        if action == "discuss":
            files = [ChatTurn(role="user", content="Deployment files:\n" + "\n\n".join(f"### {a.content.get('path')}\n{a.text}" for a in current))] if current else []
            extra = [ChatTurn(role="user", content=f"Last check:\n{check.text}")] if check else []
            return ActionOutcome(reply=self.explainer.chat(ctx, context + files + extra + turns_from(ctx.messages())))
        if action == "check":
            if not current:
                raise InvalidTransitionError("There are no deployment files yet; use Prepare deployment.")
            smoke = check.content.get("command") if check else None
            artifact, reply = self._check(ctx, code, {a.content["path"]: a.text or "" for a in current}, smoke or "")
            return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=[artifact])
        if action == "generate":
            turns = context + ([ChatTurn(role="user", content=f"Guidance: {payload.guidance}")] if payload.guidance else [])
        elif action == "revise":
            if not current:
                raise InvalidTransitionError("There is nothing to revise yet; use Prepare deployment.")
            files = ChatTurn(role="user", content="Current deployment files:\n" + "\n\n".join(f"### {a.content.get('path')}\n{a.text}" for a in current))
            turns = context + [files] + turns_from(ctx.messages())
        else:
            raise NotFoundError(action)

        out = self.deployer.ask(ctx, turns, DeployerOutput)
        new = [self._artifact(f) for f in out.files]
        ids = {a.id for a in new}
        retired = [a.model_copy(update={"retired": True}) for a in current if a.id not in ids]
        artifact, checked = self._check(ctx, code, {f.path: f.content for f in out.files}, out.smoke_command)
        reply = f"{len(new)} deployment file(s). {out.notes}\n{checked}".strip()
        return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=[*new, *retired, artifact])

    def _check(self, ctx: PhaseContext, code: list[Artifact], deploy: dict[str, str], smoke: str) -> tuple[Artifact, str]:
        code_files = {a.content["path"]: a.text or "" for a in code}
        problems = check_deployment(deploy, set(code_files))
        run: dict[str, Any] = {"ran": False}
        if smoke and ctx.sandbox is not None:
            argv = ["{python}" if i == 0 else part for i, part in enumerate(shlex.split(smoke))]
            result = ctx.sandbox.run(code_files | deploy, argv, timeout=SMOKE_TIMEOUT)
            run = {"ran": True, "exit_code": result.exit_code, "output": result.output[-4000:], "seconds": result.seconds}
            ctx.log("deployment.smoke", f"Smoke run '{smoke}': exit code {result.exit_code} ({result.seconds:.1f} s)", {"exit_code": result.exit_code})
        passed = not problems and run.get("ran") and run.get("exit_code") == 0
        lines = []
        if run.get("ran"):
            outcome = 'started and exited cleanly' if run['exit_code'] == 0 else 'failed with exit code ' + str(run['exit_code'])
            lines.append(f"Smoke run `{smoke}`: {outcome}.")
        else:
            lines.append("Smoke run not possible here (no sandbox).")
        lines += [f"Problem: {p}" for p in problems] or ["Static checks: Dockerfile and scripts copy and start only what exists."]
        lines.append("Docker itself was not run; build the image with the commands in DEPLOY.md.")
        artifact = Artifact(
            id=CHECK_ID,
            kind=ArtifactKind.DEPLOYMENT_CHECK,
            phase=self.id,
            title="Deployment check",
            content={"command": smoke, "passed": bool(passed), "problems": problems, **run},
            text="# Deployment check\n\n" + "\n".join(f"- {line}" for line in lines),
            path="reports/deployment-check.md",
            author="system:check",
        )
        return artifact, ("Check passed. " if passed else "Check found problems. ") + " ".join(lines[:-1])

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        if artifact.kind is not ArtifactKind.DEPLOYMENT_FILE or text is None:
            raise InvalidInputError("Only deployment files can be edited; the check is computed.")
        try:
            item = DeployFile(path=artifact.content["path"], purpose=artifact.content.get("purpose", ""), content=text)
        except ValidationError as err:
            raise InvalidInputError(f"Invalid file: {err.errors(include_url=False)[0]['msg']}") from err
        return self._artifact(item).model_copy(update={"author": artifact.author})

    def _files(self, ctx: PhaseContext) -> list[Artifact]:
        return [a for a in ctx.artifacts(self.id) if a.kind is ArtifactKind.DEPLOYMENT_FILE and not a.retired]

    def _artifact(self, f: DeployFile) -> Artifact:
        return Artifact(
            id=deploy_id(f.path),
            kind=ArtifactKind.DEPLOYMENT_FILE,
            phase=self.id,
            title=f.path,
            content={"path": f.path, "purpose": f.purpose, "language": "text"},
            text=f.content,
            path=f"app/{f.path}",
            author=agent_author(self.deployer.name),
        )
