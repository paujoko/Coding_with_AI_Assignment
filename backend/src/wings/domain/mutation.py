"""Injected bugs: do the tests notice when the code is wrong?

Wings changes one small spot in the generated code (a mutant: `==` becomes `!=`, a `not` is dropped,
a call is removed ...), runs the tests against it and records whether a test failed. This module is
the pure part: which spots can be changed, which few are chosen, how one run is judged and how the
result is reported. Nothing here runs code and nothing comes from a model.

A mutant changes exactly one line by source position, so the rest of the file stays byte-identical
and the line shown to the developer is the real line. Never touched: test files, `__init__.py`,
docstrings and all other string contents (f-strings included), type annotations, decorators, imports,
`if __name__ == "__main__"` blocks, `try ... except ImportError` blocks, `__dunder__` assignments,
enum values and `super()` calls. Expressions that span several lines are skipped rather than guessed.
"""

import ast
import re
from pathlib import PurePosixPath
from typing import Literal, NamedTuple

from pydantic import BaseModel, Field

from wings.domain.testreport import TestReport

DEFAULT_LIMIT = 8
MAX_LIMIT = 20

Operator = Literal["comparison", "boundary", "boolean", "logic", "negation", "arithmetic", "number", "return", "call"]
MutantOutcome = Literal["caught", "survived", "invalid"]

_COMPARE: dict[type[ast.cmpop], tuple[str, str, Operator]] = {
    ast.Eq: ("==", "!=", "comparison"),
    ast.NotEq: ("!=", "==", "comparison"),
    ast.Is: ("is", "is not", "comparison"),
    ast.IsNot: ("is not", "is", "comparison"),
    ast.In: ("in", "not in", "comparison"),
    ast.NotIn: ("not in", "in", "comparison"),
    ast.Lt: ("<", "<=", "boundary"),
    ast.LtE: ("<=", "<", "boundary"),
    ast.Gt: (">", ">=", "boundary"),
    ast.GtE: (">=", ">", "boundary"),
}
_ARITHMETIC: dict[type[ast.operator], tuple[str, str]] = {
    ast.Add: ("+", "-"),
    ast.Sub: ("-", "+"),
    ast.Mult: ("*", "/"),
    ast.Div: ("/", "*"),
    ast.FloorDiv: ("//", "*"),
}
_AUGMENTED: dict[type[ast.operator], tuple[str, str]] = {ast.Add: ("+=", "-="), ast.Sub: ("-=", "+=")}
_LOGIC: dict[type[ast.boolop], tuple[str, str]] = {ast.And: ("and", "or"), ast.Or: ("or", "and")}
_LINES = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+")
_ONLY_BRACKETS = re.compile(r"[\s()]*")
_ENUM_BASES = ("Enum", "Flag")
_IMPORT_ERRORS = ("ImportError", "ModuleNotFoundError")


class Mutant(BaseModel):
    """One injected bug: a single changed spot in one file."""

    id: str = ""  # M1, M2 ... within one selection
    path: str
    line: int  # 1-based
    column: int  # 0-based character position of the change in the line
    operator: Operator
    description: str  # "`==` became `!=`"
    original: str  # the line as it is in the file, without its line ending
    mutated: str  # the same line with the bug
    source: str = Field(exclude=True, repr=False)  # the whole file with the bug; not part of the stored data


def mutable(path: str) -> bool:
    """Program code only: Python files that are not tests and not `__init__.py`."""
    p = PurePosixPath(path)
    name = p.name
    if p.suffix != ".py" or name == "__init__.py":
        return False
    is_test = name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py" or any(part in ("tests", "test") for part in p.parts[:-1])
    return not is_test


class _Edit(NamedTuple):
    line: int
    start: int  # character positions in the line
    end: int
    new: str
    operator: Operator
    description: str
    scope: str


def _short(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_main_guard(test: ast.expr) -> bool:
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    sides = [test.left, test.comparators[0]]
    return any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides) and any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)


class _Finder(ast.NodeVisitor):
    """Walks the tree and collects every spot one of the operators can change."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.edits: list[_Edit] = []
        self.scope: list[str] = []

    # Positions: the ast counts columns in UTF-8 bytes, the lines here are text.

    def _col(self, line: int, offset: int) -> int:
        text = self.lines[line - 1]
        return offset if text.isascii() else len(text.encode("utf-8")[:offset].decode("utf-8", errors="ignore"))

    def _span(self, node: ast.expr | ast.stmt) -> tuple[int, int, int] | None:
        if node.end_lineno != node.lineno or node.end_col_offset is None or node.lineno > len(self.lines):
            return None
        return node.lineno, self._col(node.lineno, node.col_offset), self._col(node.lineno, node.end_col_offset)

    def _add(self, line: int, start: int, end: int, new: str, operator: Operator, description: str) -> None:
        self.edits.append(_Edit(line, start, end, new, operator, description, ".".join(self.scope)))

    def _swap_between(self, left: ast.expr, right: ast.expr, old: str, new: str, operator: Operator) -> None:
        """Replace the operator token `old` that stands between two operands on one line."""
        if left.end_lineno != right.lineno or left.end_col_offset is None or right.lineno > len(self.lines):
            return
        line = right.lineno
        start, end = self._col(line, left.end_col_offset), self._col(line, right.col_offset)
        between = self.lines[line - 1][start:end]
        pattern = r"\s+".join(rf"\b{re.escape(word)}\b" if word.isalpha() else re.escape(word) for word in old.split())
        found = re.search(pattern, between)
        if found is None or not _ONLY_BRACKETS.fullmatch(between[: found.start()] + between[found.end() :]):
            return
        self._add(line, start + found.start(), start + found.end(), new, operator, f"`{old}` became `{new}`")

    # Parts that are never changed

    def visit_Import(self, node: ast.Import) -> None:
        return

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        return

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        return

    def visit_TemplateStr(self, node: ast.AST) -> None:
        return

    def visit_TypeAlias(self, node: ast.AST) -> None:
        return

    def visit_arg(self, node: ast.arg) -> None:
        return  # only a name and an annotation

    def visit_If(self, node: ast.If) -> None:
        if _is_main_guard(node.test):
            return
        if _name(node.test) == "TYPE_CHECKING":
            for stmt in node.orelse:
                self.visit(stmt)
            return
        self.generic_visit(node)

    def _visit_try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            caught = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type] if handler.type else []
            if any(_name(c) in _IMPORT_ERRORS for c in caught):
                return  # optional imports: a change here would only break importing
        self.generic_visit(node)

    visit_Try = _visit_try
    visit_TryStar = _visit_try

    def visit_Assign(self, node: ast.Assign) -> None:
        if all(isinstance(t, ast.Name) and t.id.startswith("__") and t.id.endswith("__") for t in node.targets):
            return  # __all__, __version__
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        for stmt in node.body:
            self.visit(stmt)
        self.scope.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        is_enum = any(_name(base).endswith(_ENUM_BASES) for base in node.bases)
        self.scope.append(node.name)
        for stmt in node.body:
            if not (is_enum and isinstance(stmt, (ast.Assign, ast.AnnAssign))):
                self.visit(stmt)
        self.scope.pop()

    # The operators

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        for op, left, right in zip(node.ops, operands, operands[1:]):
            old, new, operator = _COMPARE[type(op)]
            self._swap_between(left, right, old, new, operator)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        old, new = _LOGIC[type(node.op)]
        for left, right in zip(node.values, node.values[1:]):
            self._swap_between(left, right, old, new, "logic")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        swap = _ARITHMETIC.get(type(node.op))
        textual = any(isinstance(s, ast.JoinedStr) or (isinstance(s, ast.Constant) and isinstance(s.value, (str, bytes))) for s in (node.left, node.right))
        if swap and not textual:  # "id-" - x would only be a TypeError, not a wrong result
            self._swap_between(node.left, node.right, swap[0], swap[1], "arithmetic")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        swap = _AUGMENTED.get(type(node.op))
        if swap:
            self._swap_between(node.target, node.value, swap[0], swap[1], "arithmetic")
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if isinstance(node.op, ast.Not) and node.lineno == node.operand.lineno and node.lineno <= len(self.lines):
            line = node.lineno
            start, end = self._col(line, node.col_offset), self._col(line, node.operand.col_offset)
            lead = self.lines[line - 1][start:end]
            found = re.match(r"not\s*", lead)
            if found and _ONLY_BRACKETS.fullmatch(lead[found.end() :]):
                self._add(line, start, start + found.end(), "", "negation", "removed `not`")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        span = self._span(node)
        if span is None:
            return
        line, start, end = span
        text = self.lines[line - 1][start:end]
        if isinstance(node.value, bool):
            new = str(not node.value)
            if text == str(node.value):
                self._add(line, start, end, new, "boolean", f"`{text}` became `{new}`")
        elif isinstance(node.value, int) and text.isascii() and text.isdigit():
            new = str(node.value + 1)
            self._add(line, start, end, new, "number", f"`{text}` became `{new}`")

    def visit_Return(self, node: ast.Return) -> None:
        value = node.value
        if value is not None and not (isinstance(value, ast.Constant) and value.value is None):
            span = self._span(value)
            if span is not None:
                line, start, end = span
                self._add(line, start, end, "None", "return", f"`return {_short(self.lines[line - 1][start:end])}` became `return None`")
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        call = node.value
        if isinstance(call, ast.Call) and not any(isinstance(n, ast.Call) and _name(n.func) == "super" for n in ast.walk(call)):
            span = self._span(node)
            if span is not None:
                line, start, end = span
                self._add(line, start, end, "pass", "call", f"the call `{_short(self.lines[line - 1][start:end])}` was removed")
        self.generic_visit(node)


def _found(path: str, text: str) -> list[tuple[Mutant, str]]:
    """Every possible mutant of one file with the function it is in, ordered by position."""
    if not mutable(path):
        return []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    lines = _LINES.findall(text)
    finder = _Finder(lines)
    finder.visit(tree)
    result: list[tuple[Mutant, str]] = []
    for edit in sorted(set(finder.edits), key=lambda e: (e.line, e.start, e.operator)):
        old = lines[edit.line - 1]
        new = old[: edit.start] + edit.new + old[edit.end :]
        source = "".join([*lines[: edit.line - 1], new, *lines[edit.line :]])
        try:
            ast.parse(source)
        except (SyntaxError, ValueError):
            continue  # never hand out a bug that is only a syntax error
        mutant = Mutant(
            path=path,
            line=edit.line,
            column=edit.start,
            operator=edit.operator,
            description=edit.description,
            original=old.rstrip("\r\n"),
            mutated=new.rstrip("\r\n"),
            source=source,
        )
        result.append((mutant, edit.scope))
    return result


def candidates(path: str, text: str) -> list[Mutant]:
    """Every single-point mutant of one file, ordered by position. Empty for files that are not program code."""
    return [m for m, _ in _found(path, text)]


def select_mutants(files: dict[str, str], limit: int = DEFAULT_LIMIT) -> list[Mutant]:
    """At most `limit` mutants (never more than MAX_LIMIT), spread over files, operators and functions.

    No randomness: the next mutant is always the one whose line, file, operator and function were used
    least so far, ties broken by position. The same files give the same mutants in the same order."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    pool = [found for path in sorted(files) for found in _found(path, files[path])]
    used: dict[tuple[str, ...], int] = {}
    chosen: list[Mutant] = []
    remaining = list(range(len(pool)))
    while remaining and len(chosen) < min(limit, MAX_LIMIT):

        def keys(index: int) -> list[tuple[str, ...]]:
            m, scope = pool[index]
            return [("line", m.path, str(m.line)), ("file", m.path), ("operator", m.operator), ("scope", m.path, scope)]

        best = min(remaining, key=lambda i: ([used.get(k, 0) for k in keys(i)], i))
        remaining.remove(best)
        for key in keys(best):
            used[key] = used.get(key, 0) + 1
        chosen.append(pool[best][0])
    chosen.sort(key=lambda m: (m.path, m.line, m.column, m.operator))
    return [m.model_copy(update={"id": f"M{i}"}) for i, m in enumerate(chosen, start=1)]


class Verdict(BaseModel):
    """What one test run says about one mutant."""

    outcome: MutantOutcome
    tests: list[str] = Field(default_factory=list)  # the tests that failed with the bug in place
    requirements: list[str] = Field(default_factory=list)  # REQ ids from those test names
    reason: str = ""  # why a run is invalid


def judge(exit_code: int, timed_out: bool, report: TestReport) -> Verdict:
    """Caught: pytest ran the tests and at least one failed (exit code 1). Survived: every test passed
    (exit code 0). Everything else is invalid and counts for neither side: the time limit was hit, or
    pytest stopped before running tests (collection error, no report)."""
    if timed_out:
        return Verdict(outcome="invalid", reason="The run hit the time limit (probably an endless loop).")
    failing = [t for t in report.tests if t.outcome in ("failed", "error")]
    if exit_code == 0 and report.tests and not failing:
        return Verdict(outcome="survived")
    if exit_code == 1 and failing:
        requirements = list(dict.fromkeys(t.requirement for t in failing if t.requirement))
        return Verdict(outcome="caught", tests=[t.name for t in failing], requirements=requirements)
    if exit_code == 2:
        return Verdict(outcome="invalid", reason="pytest stopped before any test ran (the changed file could not be loaded).")
    return Verdict(outcome="invalid", reason=f"The run gave no usable test results (exit code {exit_code}).")


class MutantResult(Mutant):
    source: str = Field(default="", exclude=True, repr=False)
    outcome: MutantOutcome
    tests: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    reason: str = ""
    seconds: float = 0.0


class StrengthReport(BaseModel):
    """How many injected bugs the tests caught. `score` leaves out the invalid runs."""

    caught: int
    survived: int
    invalid: int
    total: int
    score: float | None  # caught / (caught + survived); None when no run could be judged
    mutants: list[MutantResult]
    by_requirement: dict[str, int]  # REQ id -> injected bugs caught by a test named after it
    seconds: float
    candidates: int  # how many spots could have been changed; `total` of them were tried

    @classmethod
    def build(cls, runs: list[tuple[Mutant, Verdict, float]], requirements: list[str], candidates: int) -> "StrengthReport":
        """`requirements`: the REQ ids the test names carry, so one whose tests caught nothing shows as 0."""
        results = [MutantResult(**m.model_dump(), **v.model_dump(), seconds=s) for m, v, s in runs]
        count = {outcome: sum(r.outcome == outcome for r in results) for outcome in ("caught", "survived", "invalid")}
        judged = count["caught"] + count["survived"]
        per_requirement = dict.fromkeys(sorted(set(requirements) | {q for r in results for q in r.requirements}), 0)
        for r in results:
            for q in r.requirements:
                per_requirement[q] += 1
        return cls(
            caught=count["caught"],
            survived=count["survived"],
            invalid=count["invalid"],
            total=len(results),
            score=round(count["caught"] / judged, 4) if judged else None,
            mutants=results,
            by_requirement=per_requirement,
            seconds=round(sum(s for _, _, s in runs), 2),
            candidates=candidates,
        )


def headline(report: StrengthReport) -> str:
    judged = report.caught + report.survived
    text = f"{report.caught} of {judged} injected bugs caught" if judged else "No injected bug could be judged"
    return text + (f" ({report.invalid} not counted)" if report.invalid else "") + "."


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def strength_markdown(report: StrengthReport) -> str:
    lines = [
        "# Test strength",
        "",
        f"Wings injected {report.total} small bug(s) into the code, one at a time, and ran the tests against each "
        f"({report.seconds:.1f} s). Checked by code, no model involved.",
        "",
        f"**{headline(report)}**",
        "",
        f"Score: {report.score:.0%} (caught / (caught + survived))." if report.score is not None else "No score: no run gave a result.",
        f"{report.survived} survived: every test still passed with the bug in place.",
        f"{report.invalid} not counted: the run stopped before the tests or hit the time limit.",
        f"{report.total} of {report.candidates} possible spots were tried.",
        "",
        "| # | Where | Injected bug | Outcome | Failing tests |",
        "|---|---|---|---|---|",
    ]
    for m in report.mutants:
        tests = ", ".join(m.tests) + (f" ({', '.join(m.requirements)})" if m.requirements else "") if m.tests else m.reason
        lines.append(f"| {m.id} | {m.path} line {m.line} | {_cell(m.description)} | {m.outcome} | {_cell(tests)} |")
    for title, outcome in (("Survived", "survived"), ("Not counted", "invalid")):
        chosen = [m for m in report.mutants if m.outcome == outcome]
        if chosen:
            lines += ["", f"## {title}"]
        for m in chosen:
            lines += ["", f"{m.id}, {m.path} line {m.line}: {m.description}", "", "```diff", f"- {m.original.strip()}", f"+ {m.mutated.strip()}", "```"]
            lines += [m.reason] if m.reason else ["No test failed with this bug in place."]
    if report.by_requirement:
        lines += ["", "## Per requirement", "", "| Requirement | Injected bugs its tests caught |", "|---|---|"]
        lines += [f"| {req} | {n} |" for req, n in report.by_requirement.items()]
    return "\n".join(lines)
