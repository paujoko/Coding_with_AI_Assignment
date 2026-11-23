"""Injected bugs (mutants): which small changes Wings makes to generated code, and how a run is judged."""

import ast

import pytest

from wings.domain.mutation import MAX_LIMIT, StrengthReport, candidates, judge, mutable, select_mutants, strength_markdown
from wings.domain.testreport import TestReport, TestResult


def one(source: str, operator: str, path: str = "app/logic.py"):
    found = [m for m in candidates(path, source) if m.operator == operator]
    assert found, f"no {operator} mutant in:\n{source}"
    return found[0]


def lines_changed(before: str, after: str) -> list[int]:
    a, b = before.split("\n"), after.split("\n")
    assert len(a) == len(b)
    return [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y]


# One test per operator: the description, the line shown and the mutated file.


@pytest.mark.parametrize(
    ("source", "operator", "description", "mutated_line"),
    [
        ("def f(a, b):\n    return a == b\n", "comparison", "`==` became `!=`", "    return a != b"),
        ("def f(a, b):\n    return a != b\n", "comparison", "`!=` became `==`", "    return a == b"),
        ("def f(a):\n    return a is None\n", "comparison", "`is` became `is not`", "    return a is not None"),
        ("def f(a):\n    return a is not None\n", "comparison", "`is not` became `is`", "    return a is None"),
        ("def f(a, b):\n    return a in b\n", "comparison", "`in` became `not in`", "    return a not in b"),
        ("def f(a, b):\n    return a not in b\n", "comparison", "`not in` became `in`", "    return a in b"),
        ("def f(a, b):\n    if a < b:\n        pass\n", "boundary", "`<` became `<=`", "    if a <= b:"),
        ("def f(a, b):\n    if a <= b:\n        pass\n", "boundary", "`<=` became `<`", "    if a < b:"),
        ("def f(a, b):\n    if a > b:\n        pass\n", "boundary", "`>` became `>=`", "    if a >= b:"),
        ("def f(a, b):\n    if a >= b:\n        pass\n", "boundary", "`>=` became `>`", "    if a > b:"),
        ("def f():\n    done = True\n", "boolean", "`True` became `False`", "    done = False"),
        ("def f():\n    done = False\n", "boolean", "`False` became `True`", "    done = True"),
        ("def f(a, b):\n    if a and b:\n        pass\n", "logic", "`and` became `or`", "    if a or b:"),
        ("def f(a, b):\n    if a or b:\n        pass\n", "logic", "`or` became `and`", "    if a and b:"),
        ("def f(a):\n    if not a:\n        pass\n", "negation", "removed `not`", "    if a:"),
        ("def f(a):\n    if not (a):\n        pass\n", "negation", "removed `not`", "    if (a):"),
        ("def f(a, b):\n    x = a + b\n", "arithmetic", "`+` became `-`", "    x = a - b"),
        ("def f(a, b):\n    x = a - b\n", "arithmetic", "`-` became `+`", "    x = a + b"),
        ("def f(a, b):\n    x = a * b\n", "arithmetic", "`*` became `/`", "    x = a / b"),
        ("def f(a, b):\n    x = a / b\n", "arithmetic", "`/` became `*`", "    x = a * b"),
        ("def f(a, b):\n    x = a // b\n", "arithmetic", "`//` became `*`", "    x = a * b"),
        ("def f(a):\n    a += 1\n", "arithmetic", "`+=` became `-=`", "    a -= 1"),
        ("def f(a):\n    a -= 1\n", "arithmetic", "`-=` became `+=`", "    a += 1"),
        ("def f(a):\n    x = a[0]\n", "number", "`0` became `1`", "    x = a[1]"),
        ("def f(task):\n    x = 1\n    return task\n", "return", "`return task` became `return None`", "    return None"),
        ("def f(tasks, t):\n    tasks.append(t)\n", "call", "the call `tasks.append(t)` was removed", "    pass"),
    ],
)
def test_each_operator_changes_one_spot_and_says_what(source, operator, description, mutated_line):
    m = one(source, operator)
    assert m.description == description
    assert m.mutated == mutated_line
    assert m.original == source.split("\n")[m.line - 1]
    assert lines_changed(source, m.source) == [m.line]
    assert m.source.split("\n")[m.line - 1] == mutated_line
    ast.parse(m.source)


def test_the_rest_of_the_file_stays_byte_identical_including_odd_formatting():
    source = '# -*- coding: utf-8 -*-\r\nimport os\r\n\r\n\r\ndef  f( a,b ):   # "größer" ≥\r\n\tname = "ä" ; ok = a   <   b   # keep  spacing\r\n\treturn   ok\r\n'
    m = one(source, "boundary")
    assert m.line == 6 and m.original == '\tname = "ä" ; ok = a   <   b   # keep  spacing'
    assert m.mutated == '\tname = "ä" ; ok = a   <=   b   # keep  spacing'
    assert m.source == source.replace("a   <   b", "a   <=   b")
    for other in candidates("app/logic.py", source):
        before, after = source.split("\r\n"), other.source.split("\r\n")
        assert len(before) == len(after) and sum(x != y for x, y in zip(before, after)) == 1


def test_every_mutant_parses_and_differs_from_the_original():
    source = (
        "import json\n\n\nclass Stock:\n    def __init__(self, limit: int = 10) -> None:\n        self.items: dict[str, int] = {}\n        self.limit = limit\n\n"
        "    def add(self, name: str, count: int = 1) -> bool:\n        if count <= 0 or not name:\n            return False\n"
        "        total = self.items.get(name, 0) + count\n        if total > self.limit:\n            raise ValueError(f'more than {self.limit + 0}')\n"
        "        self.items[name] = total\n        return True\n"
    )
    found = candidates("shop/stock.py", source)
    assert {m.operator for m in found} >= {"boundary", "logic", "negation", "boolean", "arithmetic", "number", "return"}
    for m in found:
        assert m.source != source and ast.dump(ast.parse(m.source)) != ast.dump(ast.parse(source))


# Skip rules


def test_files_that_are_not_program_code_are_never_mutated():
    body = "def f(a, b):\n    return a == b\n"
    assert not mutable("tests/test_tasks.py") and candidates("tests/test_tasks.py", body) == []
    assert not mutable("todo/test_helpers.py") and not mutable("todo/helpers_test.py") and not mutable("conftest.py")
    assert not mutable("todo/__init__.py") and candidates("todo/__init__.py", body) == []
    assert not mutable("web/index.html") and candidates("web/app.js", "a == b") == []
    assert mutable("todo/service.py") and mutable("todo/__main__.py")


def test_a_file_that_does_not_parse_gives_no_mutants():
    assert candidates("todo/broken.py", "def f(:\n") == []


def test_docstrings_strings_and_fstrings_are_left_alone():
    source = (
        '"""Module: a == b, True, 1 + 2."""\n\n\n'
        'def f(a):\n    """Returns not a; 3 < 4."""\n    label = "x == 1 and not True"\n    text = f"{a + 1} is {a == 2}"\n    return label + text\n'
    )
    found = candidates("app/logic.py", source)
    assert [(m.line, m.operator) for m in found] == [(8, "return"), (8, "arithmetic")]  # only the real code of line 8


def test_string_building_is_not_turned_into_a_type_error():
    assert [m.operator for m in candidates("app/logic.py", 'def f(a):\n    x = "id-" + a\n    y = "%s" % a\n')] == []


def test_type_annotations_and_decorators_are_left_alone():
    source = (
        "from typing import Literal\n\n\n"
        "@cache(maxsize=1)\ndef f(a: Literal[1, True] = 1, *, b: 'int | None' = None) -> Literal[0]:\n"
        "    x: Literal[1, False] = 1\n    return x\n"
    )
    found = candidates("app/logic.py", source)
    # the default of `a` (line 5), the value of `x` (line 6) and the return; nothing inside an annotation or the decorator
    assert [(m.line, m.operator, m.description) for m in found] == [
        (5, "number", "`1` became `2`"),
        (6, "number", "`1` became `2`"),
        (7, "return", "`return x` became `return None`"),
    ]


def test_the_main_guard_and_import_only_code_are_left_alone():
    source = (
        "import sys\n\ntry:\n    import tomllib\n    FAST = True\nexcept ImportError:\n    FAST = False\n\n"
        "__all__ = ['main']\n__version__ = '1'\n\n\n"
        "def main() -> int:\n    return 0\n\n\n"
        'if __name__ == "__main__":\n    if len(sys.argv) > 1 and True:\n        sys.exit(main())\n'
    )
    found = candidates("app/__main__.py", source)
    assert [(m.line, m.operator) for m in found] == [(14, "number"), (14, "return")]


def test_enum_values_and_super_calls_are_left_alone():
    source = (
        "from enum import Enum\n\n\nclass Color(Enum):\n    RED = 1\n\n\n"
        "class A(Base):\n    def __init__(self) -> None:\n        super().__init__()\n        self.n = 1\n"
    )
    assert [(m.line, m.operator) for m in candidates("app/logic.py", source)] == [(11, "number")]


def test_expressions_spanning_lines_are_skipped_rather_than_guessed():
    source = "def f(a, b):\n    return (a\n            == b)\n"
    assert [m.operator for m in candidates("app/logic.py", source)] == []


# Selection

FILES = {
    "shop/cart.py": (
        "class Cart:\n    def __init__(self) -> None:\n        self.items = []\n\n"
        "    def add(self, item, count=1):\n        if count < 1:\n            raise ValueError('count')\n        self.items.append((item, count))\n        return len(self.items)\n\n"
        "    def total(self, prices):\n        total = 0\n        for item, count in self.items:\n            total += prices[item] * count\n        return total\n\n"
        "    def empty(self):\n        return not self.items\n"
    ),
    "shop/discount.py": (
        "def discount(total, member):\n    if member and total >= 100:\n        return total - 10\n    if total == 0:\n        return 0\n    return total\n"
    ),
    "shop/flags.py": "ENABLED = True\n\n\ndef enabled():\n    return ENABLED\n",
    "shop/__init__.py": "X = 1 == 1\n",
    "tests/test_cart.py": "def test_req_001_x():\n    assert 1 == 1\n",
}


def test_selection_is_deterministic_and_spread_over_files_and_operators():
    first = select_mutants(FILES, limit=8)
    again = select_mutants(dict(reversed(list(FILES.items()))), limit=8)
    assert [m.model_dump() for m in first] == [m.model_dump() for m in again]
    assert [m.source for m in first] == [m.source for m in again]
    assert len(first) == 8 and [m.id for m in first] == [f"M{i}" for i in range(1, 9)]
    assert {m.path for m in first} == {"shop/cart.py", "shop/discount.py", "shop/flags.py"}
    assert len({m.operator for m in first}) >= 6
    assert len({(m.path, m.line) for m in first}) == 8  # one bug per line while there are lines left
    assert [(m.path, m.line, m.column) for m in first] == sorted((m.path, m.line, m.column) for m in first)


def test_the_limit_is_respected_and_capped():
    assert len(select_mutants(FILES, limit=3)) == 3
    assert {m.path for m in select_mutants(FILES, limit=3)} == {"shop/cart.py", "shop/discount.py", "shop/flags.py"}
    everything = select_mutants(FILES, limit=500)
    assert len(everything) <= MAX_LIMIT
    assert select_mutants({"tests/test_cart.py": FILES["tests/test_cart.py"]}, limit=8) == []
    with pytest.raises(ValueError):
        select_mutants(FILES, limit=0)


def test_a_mutant_as_data_does_not_carry_the_whole_file():
    m = select_mutants(FILES, limit=1)[0]
    assert set(m.model_dump()) == {"id", "path", "line", "column", "operator", "description", "original", "mutated"}


# Judging one run


def report(*outcomes: tuple[str, str]) -> TestReport:
    return TestReport(tests=[TestResult(name=n, outcome=o) for n, o in outcomes])  # type: ignore[arg-type]


def test_a_failing_test_catches_the_bug_and_names_test_and_requirement():
    verdict = judge(1, False, report(("test_req_001_add", "passed"), ("test_req_003_done", "failed"), ("test_req_003_missing", "error"), ("test_helper", "failed")))
    assert verdict.outcome == "caught"
    assert verdict.tests == ["test_req_003_done", "test_req_003_missing", "test_helper"]
    assert verdict.requirements == ["REQ-003"]


def test_all_tests_passing_means_the_bug_survived():
    verdict = judge(0, False, report(("test_req_001_add", "passed"), ("test_req_002_list", "skipped")))
    assert (verdict.outcome, verdict.tests, verdict.requirements) == ("survived", [], [])


def test_runs_that_say_nothing_are_invalid_and_say_why():
    assert judge(124, True, report(("test_req_001_add", "failed"))).outcome == "invalid"
    assert "time limit" in judge(124, True, report()).reason
    collection = judge(2, False, report(("tests.test_tasks", "error")))
    assert collection.outcome == "invalid" and "before any test" in collection.reason and collection.tests == []
    assert judge(1, False, TestReport(errors=1)).outcome == "invalid"  # no JUnit report
    assert judge(0, False, report()).outcome == "invalid"  # exit 0 without a single test result proves nothing
    assert judge(5, False, report()).outcome == "invalid"
    assert judge(1, False, report(("test_req_001_add", "passed"))).outcome == "invalid"  # exit 1 but no failing test recorded


# The report


def strength() -> StrengthReport:
    mutants = select_mutants(FILES, limit=4)
    verdicts = [
        judge(1, False, report(("test_req_001_add", "failed"), ("test_req_002_total", "failed"))),
        judge(0, False, report(("test_req_001_add", "passed"))),
        judge(124, True, report()),
        judge(1, False, report(("test_req_001_add", "failed"))),
    ]
    return StrengthReport.build(list(zip(mutants, verdicts, [0.5, 0.4, 10.0, 0.6])), requirements=["REQ-001", "REQ-002", "REQ-003"], candidates=30)


def test_the_report_counts_and_scores_without_the_invalid_ones():
    r = strength()
    assert (r.caught, r.survived, r.invalid, r.total) == (2, 1, 1, 4)
    assert r.score == pytest.approx(2 / 3, abs=1e-4)  # stored rounded to four places
    assert r.by_requirement == {"REQ-001": 2, "REQ-002": 1, "REQ-003": 0}
    assert [m.outcome for m in r.mutants] == ["caught", "survived", "invalid", "caught"]
    assert r.mutants[0].tests == ["test_req_001_add", "test_req_002_total"] and r.mutants[0].requirements == ["REQ-001", "REQ-002"]
    assert r.seconds == pytest.approx(11.5) and r.candidates == 30
    content = r.model_dump()
    assert {"caught", "survived", "invalid", "total", "score", "mutants", "by_requirement", "seconds", "candidates"} <= set(content)
    assert "source" not in content["mutants"][0]


def test_no_score_when_nothing_could_be_judged():
    r = StrengthReport.build([(select_mutants(FILES, limit=1)[0], judge(124, True, report()), 10.0)], requirements=[], candidates=1)
    assert r.score is None and "No score" in strength_markdown(r)


def test_the_markdown_shows_each_bug_its_outcome_and_the_surviving_lines():
    r = strength()
    text = strength_markdown(r)
    assert "2 of 3 injected bugs caught" in text and "1 not counted" in text
    survivor = next(m for m in r.mutants if m.outcome == "survived")
    assert f"- {survivor.original.strip()}" in text and f"+ {survivor.mutated.strip()}" in text
    assert f"{survivor.path} line {survivor.line}" in text
    assert "| REQ-003 | 0 |" in text and "test_req_002_total" in text
    assert "\u2014" not in text
