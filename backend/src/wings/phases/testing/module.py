"""P5 Testing wing: tests from the requirements, run for real, failures explained.

- generate: the tester writes pytest files (`test-<slug>`, kind test_file); names carry REQ ids.
- run: code and tests run in the Sandbox port; the JUnit report becomes the `test-report` artifact.
  The result is computed, never generated (domain/testreport.py).
- explain: the debugger decides whether code or test is wrong; a wrong test is fixed here, a code
  fix is offered as a next action for the code generation wing.
"""

from typing import Any, ClassVar

from pydantic import BaseModel, Field, ValidationError

from wings.application.agent import LLMAgent, document_turns, turns_from
from wings.application.phase import ActionOutcome, ActionSpec, AgentInfo, PhaseContext, PhaseModule
from wings.application.ports import ChatTurn
from wings.application.registry import load_prompt
from wings.application.tools import CHECK_PYTHON
from wings.domain.artifacts import Artifact, ArtifactKind, agent_author
from wings.domain.diagrams import describe_set
from wings.domain.errors import InvalidInputError, InvalidTransitionError, NotFoundError
from wings.domain.phases import PhaseId, PhaseStatus
from wings.domain.testreport import Gap, TestReport, apply_gaps, gaps_markdown, parse_junit
from wings.domain.trace import fresh_report
from wings.phases.testing.schema import DebuggerOutput, TesterOutput, TestFile, test_file_id

REPORT_ID = "test-report"
GAPS_ID = "test-gaps"
CODE_GAPS_ID = "code-gaps"  # written by the code generation wing
JUNIT = "wings-junit.xml"
RUN_TIMEOUT = 120.0


class GenerateInput(BaseModel):
    guidance: str = Field("", description="Optional: what the tests should focus on")


class NoInput(BaseModel):
    pass


class ExplainInput(BaseModel):
    test: str = Field("", description="Optional: the failing test to look at; empty means all failures")


class DiscussInput(BaseModel):
    question: str = Field(min_length=1, description="Ask about the tests or the results; nothing is changed")


class TestingPhase(PhaseModule):
    __test__ = False

    id: ClassVar[PhaseId] = PhaseId.TESTING
    title: ClassVar[str] = "Testing"
    summary: ClassVar[str] = "Writes tests from the requirements, runs them for real and explains failures."
    requires: ClassVar[list[PhaseId]] = [PhaseId.CODEGEN]

    def __init__(self) -> None:
        pkg = __package__ or "wings.phases.testing"
        self.tester = LLMAgent("tester", "Tester: writes pytest tests from the acceptance criteria", load_prompt(pkg, "tester.md"), tier="mid")
        self.debugger = LLMAgent("debugger", "Debugger: explains failing tests and says whether code or test is wrong", load_prompt(pkg, "debugger.md"), tier="frontier")
        self.explainer = LLMAgent("tester", "Explains the tests", load_prompt(pkg, "discuss.md"), tier="mid")

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="generate", label="Write tests", description="Write tests from the requirements and the code.", input_model=GenerateInput, message_field="guidance"),
            ActionSpec(name="run", label="Run tests", description="Run all tests for real and record the results.", input_model=NoInput),
            ActionSpec(name="explain", label="Explain failures", description="Find out whether the code or the test is wrong.", input_model=ExplainInput, message_field="test"),
            ActionSpec(name="discuss", label="Discuss", description="Ask about the tests or the results.", input_model=DiscussInput, message_field="question"),
        ]

    @property
    def agents(self) -> list[AgentInfo]:
        return [AgentInfo(name=a.name, role=a.role, tier=a.tier) for a in (self.tester, self.debugger)]

    def approval_problem(self, artifacts: list[Artifact]) -> str | None:
        """Tests are approved only when they ran green on the current code and tests (checked by code)."""
        live = [a for a in artifacts if not a.retired]
        if not any(a.kind is ArtifactKind.TEST_REPORT for a in live):
            return "Run the tests before approving: the result must come from a real run."
        report = fresh_report(live, ArtifactKind.TEST_REPORT, (ArtifactKind.SOURCE_FILE, ArtifactKind.TEST_FILE))
        if report is None:
            return "Code or tests changed since the last run. Run the tests again before approving."
        if not report.content.get("green"):
            return "Some tests do not pass. Fix them (Explain failures helps) and run them again before approving."
        return None

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        code = self._code(ctx)
        if not code:
            raise InvalidTransitionError("There is no code to test yet; finish code generation first.")
        tests = self._tests(ctx)
        report = next((a for a in ctx.artifacts(self.id) if a.id == REPORT_ID and not a.retired), None)
        if action == "generate":
            return self._generate(ctx, payload, code)
        if action == "run":
            if not tests:
                raise InvalidTransitionError("There are no tests yet; use Write tests first.")
            return self._run(ctx, code, tests)
        if action == "explain":
            return self._explain(ctx, payload, code, tests, report)
        if action == "discuss":
            extra = [ChatTurn(role="user", content=f"Latest results:\n{report.text}")] if report else []
            files = [ChatTurn(role="user", content=self._listing("Tests", tests))] if tests else []
            return ActionOutcome(reply=self.explainer.chat(ctx, files + extra + turns_from(ctx.messages())))
        raise NotFoundError(action)

    def _generate(self, ctx: PhaseContext, payload: Any, code: list[Artifact]) -> ActionOutcome:
        requirements = next((a for a in ctx.artifacts(PhaseId.REQUIREMENTS) if a.kind is ArtifactKind.REQUIREMENTS), None)
        design = ctx.current_design()
        turns = [
            ChatTurn(role="user", content=f"Approved requirements:\n{requirements.text if requirements else ''}"),
            ChatTurn(role="user", content="Design:\n" + describe_set([(d.content.get("kind", ""), d.title, d.text or "") for d in design])),
            ChatTurn(role="user", content=self._listing("Code under test", code)),
        ]
        if payload.guidance:
            turns.append(ChatTurn(role="user", content=f"Guidance: {payload.guidance}"))
        out = self.tester.ask(ctx, document_turns(ctx, PhaseId.REQUIREMENTS) + turns, TesterOutput, tools=[CHECK_PYTHON])
        new = [self._test_artifact(f, self.tester.name) for f in out.files]
        ids = {a.id for a in new}
        retired = [a.model_copy(update={"retired": True}) for a in self._tests(ctx) if a.id not in ids]
        count = sum(f.content.count("def test_") for f in out.files)
        reply = f"{count} test(s) in {len(new)} file(s). {out.notes}".strip()
        if out.gaps:
            reply += "\nNot fully tested (these will not count as verified):\n- " + "\n- ".join(f"{g.requirement}: {g.reason}" for g in out.gaps)
        return ActionOutcome(
            status=PhaseStatus.DRAFT,
            reply=reply,
            artifacts=[*new, *retired, self._gaps_artifact(out.gaps)],
            data={"next_actions": [{"label": "Run tests", "phase": self.id.value, "action": "run", "input": {}}]},
        )

    def _run(self, ctx: PhaseContext, code: list[Artifact], tests: list[Artifact]) -> ActionOutcome:
        if ctx.sandbox is None:
            raise InvalidTransitionError("This installation cannot run code (no sandbox configured).")
        files = {a.content["path"]: a.text or "" for a in code} | {a.content["path"]: a.text or "" for a in tests}
        argv = ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={JUNIT}", "tests"]
        result = ctx.sandbox.run(files, argv, timeout=RUN_TIMEOUT, collect=[JUNIT])
        report = parse_junit(result.collected.get(JUNIT, ""), output=result.output[-6000:])
        if result.timed_out:
            report = report.model_copy(update={"errors": report.errors + 1})
        ctx.log("tests.run", f"pytest: {report.passed} passed, {report.failed} failed, {report.errors} errors ({result.seconds:.1f} s)", {"exit_code": result.exit_code})
        verified = apply_gaps(report.by_requirement(), code_gaps=self._declared(ctx, PhaseId.CODEGEN, CODE_GAPS_ID), test_gaps=self._declared(ctx, self.id, GAPS_ID))
        artifact = self._report_artifact(report, result.exit_code, result.seconds, verified)
        passed = sorted(r for r, v in verified.items() if v == "passed")
        held_back = sorted(r for r, v in verified.items() if v in ("partial", "not_met"))
        if report.green:
            reply = f"All {report.passed} tests pass. Verified: {', '.join(passed) or 'no REQ ids in test names'}."
            if held_back:
                labels = {"partial": "only partly tested", "not_met": "not met by the code"}
                reply += " Not verified despite passing tests: " + ", ".join(f"{r} ({labels[verified[r]]})" for r in held_back) + "."
            actions = []
        else:
            failing = [t for t in report.tests if t.outcome in ("failed", "error")]
            reply = f"{report.passed} passed, {report.failed} failed, {report.errors} errors."
            if failing:
                reply += "\n" + "\n".join(f"- {t.name}: {t.message.splitlines()[0] if t.message else t.outcome}" for t in failing[:8])
            elif not report.tests:
                reply += "\nNo test results: pytest could not collect or run the tests. See the output in the report."
            actions = [{"label": "Explain the failures", "phase": self.id.value, "action": "explain", "input": {}}]
        return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=[artifact], data={"verified": verified, "next_actions": actions})

    def _explain(self, ctx: PhaseContext, payload: Any, code: list[Artifact], tests: list[Artifact], report: Artifact | None) -> ActionOutcome:
        if report is None:
            raise InvalidTransitionError("Run the tests first.")
        failing = [t for t in report.content.get("tests", []) if t["outcome"] in ("failed", "error")]
        if payload.test:
            failing = [t for t in failing if payload.test in t["name"]] or failing
        if not failing and not report.content.get("errors"):
            raise InvalidTransitionError("Nothing failed in the last run.")
        summary = "\n".join(f"{t['name']}: {t['message']}" for t in failing) or "pytest could not run the tests."
        turns = [
            ChatTurn(role="user", content=f"Failing tests:\n{summary}\n\nOutput (end):\n{report.content.get('output', '')[-3000:]}"),
            ChatTurn(role="user", content=self._listing("Tests", tests)),
            ChatTurn(role="user", content=self._listing("Code under test", code)),
        ]
        requirements = next((a for a in ctx.artifacts(PhaseId.REQUIREMENTS) if a.kind is ArtifactKind.REQUIREMENTS), None)
        if requirements:
            turns.insert(0, ChatTurn(role="user", content=f"Requirements:\n{requirements.text}"))
        out = self.debugger.ask(ctx, turns, DebuggerOutput, tools=[CHECK_PYTHON])
        reply = f"{out.diagnosis}\nWhere the mistake is: {out.cause}. Fix: {out.fix}"
        if out.cause == "test" and out.test_files:
            fixed = [self._test_artifact(f, self.debugger.name) for f in out.test_files]
            reply += "\nI corrected the test(s); run them again."
            action = {"label": "Run tests", "phase": self.id.value, "action": "run", "input": {}}
            return ActionOutcome(status=PhaseStatus.DRAFT, reply=reply, artifacts=fixed, data={"cause": "test", "next_actions": [action]})
        actions = []
        if out.cause == "code":
            actions = [{"label": "Send the fix to Code generation", "phase": PhaseId.CODEGEN.value, "action": "revise", "input": {"feedback": out.fix}}]
        return ActionOutcome(reply=reply, data={"cause": out.cause, "fix": out.fix, "next_actions": actions})

    def apply_developer_edit(self, artifact: Artifact, content: dict[str, Any] | None, text: str | None) -> Artifact:
        if artifact.kind is not ArtifactKind.TEST_FILE or text is None:
            raise InvalidInputError("Only test files can be edited; results come from running the tests.")
        try:
            item = TestFile(path=artifact.content["path"], purpose=artifact.content.get("purpose", ""), covers=artifact.covers, content=text)
        except ValidationError as err:
            raise InvalidInputError(f"Invalid test file: {err.errors(include_url=False)[0]['msg']}") from err
        return self._test_artifact(item, "").model_copy(update={"author": artifact.author})

    # Helpers

    def _code(self, ctx: PhaseContext) -> list[Artifact]:
        return [a for a in ctx.artifacts(PhaseId.CODEGEN) if a.kind is ArtifactKind.SOURCE_FILE and not a.retired]

    def _tests(self, ctx: PhaseContext) -> list[Artifact]:
        return [a for a in ctx.artifacts(self.id) if a.kind is ArtifactKind.TEST_FILE and not a.retired]

    @staticmethod
    def _listing(title: str, files: list[Artifact]) -> str:
        return f"{title}:\n" + "\n\n".join(f"### {a.content.get('path')}\n{a.text}" for a in files)

    def _test_artifact(self, f: TestFile, agent: str) -> Artifact:
        return Artifact(
            id=test_file_id(f.path),
            kind=ArtifactKind.TEST_FILE,
            phase=self.id,
            title=f.path,
            content={"path": f.path, "purpose": f.purpose, "language": "python"},
            text=f.content,
            path=f"app/{f.path}",
            covers=f.covers,
            author=agent_author(agent) if agent else "developer",
        )

    @staticmethod
    def _declared(ctx: PhaseContext, phase: PhaseId, artifact_id: str) -> list[Gap]:
        found = next((a for a in ctx.artifacts(phase) if a.id == artifact_id and not a.retired), None)
        return [Gap.model_validate(g) for g in (found.content.get("gaps", []) if found else [])]

    def _gaps_artifact(self, gaps: list[Gap]) -> Artifact:
        return Artifact(
            id=GAPS_ID,
            kind=ArtifactKind.KNOWN_GAPS,
            phase=self.id,
            title="Requirements the tests do not fully check",
            content={"gaps": [g.model_dump() for g in gaps]},
            text=gaps_markdown("Requirements the tests do not fully check", gaps),
            path="reports/test-gaps.md",
            author=agent_author(self.tester.name),
        )

    def _report_artifact(self, report: TestReport, exit_code: int, seconds: float, verified: dict[str, str]) -> Artifact:
        lines = ["# Test results", "", f"{report.passed} passed, {report.failed} failed, {report.errors} errors ({seconds:.1f} s).", ""]
        lines += [f"- {t.outcome.upper()} {t.name}" + (f": {t.message.splitlines()[0]}" if t.message else "") for t in report.tests]
        return Artifact(
            id=REPORT_ID,
            kind=ArtifactKind.TEST_REPORT,
            phase=self.id,
            title="Test results",
            content={
                "tests": [t.model_dump() | {"requirement": t.requirement} for t in report.tests],
                "passed": report.passed,
                "failed": report.failed,
                "errors": report.errors,
                "green": report.green,
                "verified": verified,
                "exit_code": exit_code,
                "seconds": seconds,
                "output": report.output,
            },
            text="\n".join(lines),
            path="reports/test-results.md",
            author="system:pytest",
        )
