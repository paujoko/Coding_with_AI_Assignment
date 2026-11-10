"""Test results as data. Parsed from pytest's JUnit XML: the outcome comes from running the tests, never from an LLM.

Test names carry the requirement they check (`test_req_003_...`), which links results to the trace.
"""

import re
import xml.etree.ElementTree as ET
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Outcome = Literal["passed", "failed", "error", "skipped"]
# What the trace shows per requirement: a test outcome, or a declared gap that keeps it from counting as verified.
Verdict = Literal["passed", "failed", "error", "skipped", "partial", "not_met"]
_REQ = re.compile(r"req_?(\d{3})", re.IGNORECASE)


class TestResult(BaseModel):
    __test__ = False  # not a pytest test class

    name: str
    classname: str = ""
    outcome: Outcome
    message: str = ""

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
