"""Test results as data: the outcome comes from running the tests, never from an LLM.

Two sources: the events Wings' pytest plugin writes while the tests run (`parse_events`: file and line
of every failure, and they survive a run that is stopped), and pytest's JUnit XML (`parse_junit`, the
fallback). Test names carry the requirement they check (`test_req_003_...`), which links results to the trace.
"""

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Outcome = Literal["passed", "failed", "error", "skipped"]
# What the trace shows per requirement: a test outcome, or a declared gap that keeps it from counting as verified.
Verdict = Literal["passed", "failed", "error", "skipped", "partial", "not_met"]
_REQ = re.compile(r"req_?(\d{3})", re.IGNORECASE)
MAX_FRAMES = 6  # project lines kept per failure, the innermost last
# A traceback line in pytest's own style ("tests/test_a.py:12: in ...") or Python's ('File "x.py", line 12').
_LOCATION = re.compile(r'^\s*(?:File "(?P<quoted>[^"]+\.py)", line (?P<qline>\d+)|(?P<path>[^\s:"][^:\n"]*\.py):(?P<line>\d+)(?::|$))', re.MULTILINE)


class Frame(BaseModel):
    """One line of a traceback inside the project's own files."""

    path: str
    line: int
    code: str = ""  # the source line, read from the files that ran


class TestResult(BaseModel):
    __test__ = False  # not a pytest test class

    name: str
    classname: str = ""
    outcome: Outcome
    message: str = ""
    path: str = ""  # the test's file; empty when only JUnit XML was available
    where: list[Frame] = Field(default_factory=list)  # project lines of the failure, the innermost last

    @property
    def requirement(self) -> str | None:
        m = _REQ.search(self.name)
        return f"REQ-{m.group(1)}" if m else None


class TestReport(BaseModel):
    __test__ = False

    tests: list[TestResult] = Field(default_factory=list)
    errors: int = 0  # collection errors and broken runs count here too
    output: str = ""  # the end of the console output, for the debugger and the developer

    @property
    def passed(self) -> int:
        return sum(t.outcome == "passed" for t in self.tests)

    @property
    def failed(self) -> int:
        return sum(t.outcome == "failed" for t in self.tests)

    @property
    def green(self) -> bool:
        return bool(self.tests) and self.failed == 0 and self.errors == 0

    def by_requirement(self) -> dict[str, Outcome]:
        """REQ id -> the worst outcome of its tests."""
        rank = {"passed": 0, "skipped": 1, "failed": 2, "error": 3}
        result: dict[str, Outcome] = {}
        for t in self.tests:
            if t.requirement and rank[t.outcome] >= rank.get(result.get(t.requirement, "passed"), 0):
                result[t.requirement] = t.outcome
        return result


def parse_junit(xml_text: str, output: str = "") -> TestReport:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return TestReport(errors=1, output=output)
    tests: list[TestResult] = []
    errors = 0
    for case in root.iter("testcase"):
        outcome: Outcome = "passed"
        message = ""
        for tag in ("failure", "error", "skipped"):
            el = case.find(tag)
            if el is not None:
                outcome = "failed" if tag == "failure" else tag if tag == "error" else "skipped"  # type: ignore[assignment]
                message = (el.get("message") or el.text or "").strip()[:2000]
                break
        if outcome == "error":
            errors += 1
        tests.append(TestResult(name=case.get("name", ""), classname=case.get("classname", ""), outcome=outcome, message=message))
    for suite in root.iter("testsuite"):
        errors += 0 if tests else int(suite.get("errors", "0") or 0)
    return TestReport(tests=tests, errors=errors, output=output)


def _norm(path: str) -> str:
    path = path.replace("\\", "/")
    return path[2:] if path.startswith("./") else path


def _frames(event: dict[str, Any], files: dict[str, str]) -> list[Frame]:
    """The event's traceback lines that lie in the project, each with its source line."""
    raw = [(_norm(str(f.get("path", ""))), int(f.get("line", 0))) for f in event.get("frames") or [] if isinstance(f, dict)]
    if not raw:
        raw = [(_norm(m["quoted"] or m["path"]), int(m["qline"] or m["line"])) for m in _LOCATION.finditer(str(event.get("text", "")))]
    found: list[Frame] = []
    for path, line in raw:
        if path not in files:
            continue
        lines = files[path].splitlines()
        frame = Frame(path=path, line=line, code=lines[line - 1].strip() if 0 < line <= len(lines) else "")
        if not found or found[-1] != frame:
            found.append(frame)
    return found[-MAX_FRAMES:]


def _message(event: dict[str, Any]) -> str:
    if event.get("message"):
        return str(event["message"]).strip()[:2000]
    lines = [line.strip() for line in str(event.get("text", "")).splitlines() if line.strip()]
    errors = [line[1:].strip() for line in lines if line.startswith("E ")]
    return (errors[0] if errors else lines[-1] if lines else "")[:2000]


def _definition(nodeid: str, files: dict[str, str]) -> list[Frame]:
    """Where the test function is defined: the place to look when it never finished."""
    path, _, rest = nodeid.partition("::")
    name = rest.rsplit("::", 1)[-1].split("[", 1)[0]
    for i, line in enumerate(files.get(path, "").splitlines(), start=1):
        if line.lstrip().startswith(f"def {name}("):
            return [Frame(path=path, line=i, code=line.strip())]
    return []


def parse_events(text: str, files: dict[str, str], output: str = "", timed_out: bool = False) -> TestReport | None:
    """Results from the plugin's JSON lines (phases/testing/pytest_events.py); None when it wrote nothing.

    `files` are the files that ran (path -> source), so a failure is shown only with lines in the project.
    A test that started but never finished is an error: the plugin stopped it after its time limit
    (event "slow"), or the whole run was stopped (`timed_out`)."""
    events = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue  # the last line of a stopped run can be cut off
        if isinstance(event, dict) and event.get("event"):
            events.append(event)
    if not events:
        return None
    order: list[str] = []
    phases: dict[str, dict[str, dict[str, Any]]] = {}  # nodeid -> when -> report event
    collect: list[dict[str, Any]] = []
    slow: dict[str, Any] = {}
    for event in events:
        nodeid = str(event.get("nodeid", ""))
        if event["event"] == "start" and nodeid not in phases:
            order.append(nodeid)
            phases[nodeid] = {}
        elif event["event"] == "report":
            if nodeid not in phases:
                order.append(nodeid)
                phases[nodeid] = {}
            phases[nodeid][str(event.get("when", "call"))] = event
        elif event["event"] == "collect" and event.get("outcome") == "failed":
            collect.append(event)
        elif event["event"] == "slow":
            slow = event

    tests = [TestResult(name=_norm(e.get("nodeid", "")) or "tests", path=_norm(e.get("nodeid", "")), outcome="error", message=_message(e), where=_frames(e, files)) for e in collect]
    unfinished = False
    for nodeid in order:
        path, _, rest = nodeid.partition("::")
        parts = rest.split("::")
        base = TestResult(name=parts[-1], classname=".".join([path.removesuffix(".py").replace("/", "."), *parts[:-1]]), path=path, outcome="passed")
        setup, call, teardown = (phases[nodeid].get(w) for w in ("setup", "call", "teardown"))
        if setup and setup.get("outcome") == "failed":
            result = base.model_copy(update={"outcome": "error", "message": _message(setup), "where": _frames(setup, files)})
        elif setup and setup.get("outcome") == "skipped":
            result = base.model_copy(update={"outcome": "skipped", "message": _message(setup)})
        elif call is None:
            unfinished = True
            if slow.get("nodeid") == nodeid:
                why = f"Did not finish within {float(slow.get('seconds', 0)):g} s; the run stopped here and later tests did not run."
            elif timed_out:
                why = "Did not finish: the whole run hit its time limit while this test ran."
            else:
                why = "Did not finish: the test process ended while this test ran."
            result = base.model_copy(update={"outcome": "error", "message": why, "where": _definition(nodeid, files)})
        elif call.get("outcome") != "passed":
            result = base.model_copy(update={"outcome": call["outcome"], "message": _message(call), "where": _frames(call, files)})
        elif teardown and teardown.get("outcome") == "failed":
            result = base.model_copy(update={"outcome": "error", "message": _message(teardown), "where": _frames(teardown, files)})
        else:
            result = base
        tests.append(result)
    errors = sum(t.outcome == "error" for t in tests) + (1 if timed_out and not unfinished else 0)
    return TestReport(tests=tests, errors=errors, output=output)


def describe_failures(tests: list[TestResult], limit: int = 12) -> str:
    """The failing tests for an agent: name, file, first message line and the project lines, innermost last."""
    failing = [t for t in tests if t.outcome in ("failed", "error")]
    blocks = []
    for i, t in enumerate(failing[:limit], start=1):
        lines = [f"{i}. {t.name}{f' ({t.path})' if t.path and t.path != t.name else ''}: {t.outcome}"]
        if t.message:
            lines.append(f"   {t.message.splitlines()[0]}")
        lines += [f"   {f.path}:{f.line}  {f.code}".rstrip() for f in t.where]
        blocks.append("\n".join(lines))
    if len(failing) > limit:
        blocks.append(f"... and {len(failing) - limit} more failing tests.")
    return "\n".join(blocks)


class Gap(BaseModel):
    """A requirement an agent says it could not meet (coder) or not fully check (tester), and why."""

    requirement: str = Field(description="The REQ id, e.g. REQ-015")
    reason: str = Field(description="Why, in one sentence")

    @field_validator("requirement")
    @classmethod
    def _req(cls, value: str) -> str:
        m = _REQ.search(value.replace("-", "_"))
        if not m:
            raise ValueError(f"'{value}' is not a requirement id like REQ-015")
        return f"REQ-{m.group(1)}"


def apply_gaps(verified: dict[str, str], code_gaps: list[Gap], test_gaps: list[Gap]) -> dict[str, str]:
    """Passing tests verify a requirement only if nobody declared a gap for it (real run s03: REQ-015,
    "runs in the browser", showed as verified for a terminal program). Code gaps win: `not_met` is shown
    even without a test; a tester's gap turns `passed` into `partial`."""
    result = dict(verified)
    for gap in test_gaps:
        if result.get(gap.requirement) == "passed":
            result[gap.requirement] = "partial"
    for gap in code_gaps:
        result[gap.requirement] = "not_met"
    return result


def gaps_markdown(title: str, gaps: list[Gap]) -> str:
    lines = [f"# {title}", ""]
    lines += [f"- {g.requirement}: {g.reason}" for g in gaps] or ["None declared."]
    return "\n".join(lines)
