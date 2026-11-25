"""JavaScript tests run with Node's built-in test runner (`node --test`), read from its TAP output (ADR 0020).

Wings runs one test file per Node run, so every result belongs to that file. Nothing here comes from a
model: `parse_tap` turns the TAP text into the same `TestResult` the pytest path uses (runner "node"),
`js_exports` says whether Node can import a code file at all, `count_js_tests` and `js_imports` let the
tester's answer be checked before anything runs. Pure: standard library and Pydantic only.
"""

import re
from pathlib import PurePosixPath

from wings.domain.testreport import MAX_FRAMES, Frame, Outcome, TestResult

JS_TEST_SUFFIXES = (".test.js", ".test.mjs", ".test.cjs")
JS_SOURCE_SUFFIXES = (".js", ".mjs", ".cjs")
# Modules a node:test file may load without npm: the `node:` ones and the core names without the prefix.
CORE_MODULES = {"assert", "assert/strict", "test", "fs", "fs/promises", "path", "util", "events", "url", "os", "timers", "timers/promises", "vm", "buffer", "crypto"}


def is_js_test(path: str) -> bool:
    return path.startswith("tests/") and path.endswith(JS_TEST_SUFFIXES)


def is_js_source(path: str) -> bool:
    """A JavaScript file of the program (not a test)."""
    return path.endswith(JS_SOURCE_SUFFIXES) and not path.endswith(JS_TEST_SUFFIXES) and "tests" not in PurePosixPath(path).parts[:-1]


def _strip(text: str, keep_strings: bool = False) -> str:
    """The code without comments, and without the contents of string literals unless `keep_strings`.
    Line breaks stay, so line numbers do not move. Regular expression literals are not recognised."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
        elif c == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            block = text[i : n if end < 0 else end + 2]
            out.append("\n" * block.count("\n"))
            i += len(block)
        elif c in "'\"`":
            j = i + 1
            while j < n and text[j] != c and not (c != "`" and text[j] == "\n"):
                j += 2 if text[j] == "\\" else 1
            literal = text[i : j + 1]
            out.append(literal if keep_strings else c + re.sub(r"[^\n]", " ", literal[1:-1]) + c)
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


_IDENT = r"[A-Za-z_$][\w$]*"


def js_exports(text: str) -> list[str]:
    """The names a JavaScript file gives to whoever imports it (CommonJS `module.exports`/`exports.x`, or
    ES `export`). An empty list means Node can load the file but reach nothing in it: a browser script
    whose functions are globals."""
    code = _strip(text)
    names: set[str] = set()
    for m in re.finditer(r"\bmodule\.exports\s*=\s*\{([^{}]*)\}", code):
        for item in m.group(1).split(","):
            head = re.match(rf"\s*(?:async\s+)?\*?\s*({_IDENT})", item)
            if head:
                names.add(head.group(1))
    for m in re.finditer(rf"\bmodule\.exports\s*=\s*({_IDENT})\s*;?", code):
        if m.group(1) not in ("function", "class", "require"):
            names.add(m.group(1))
    names.update(re.findall(rf"\b(?:module\.)?exports\.({_IDENT})\s*=", code))
    names.update(re.findall(rf"\bexport\s+(?:async\s+)?(?:function\s*\*?|class|const|let|var)\s+({_IDENT})", code))
    for m in re.finditer(r"\bexport\s*\{([^}]*)\}", code):
        for item in m.group(1).split(","):
            parts = item.split()
            if parts:
                names.add(parts[-1])
    if re.search(r"\bexport\s+default\b", code):
        names.add("default")
    return sorted(names)


_TEST_CALL = re.compile(r"(?<![\w.$])(?:test|it)(?:\.(?:skip|todo|only))?\s*\(|\bt\.test\s*\(")


def count_js_tests(text: str) -> int:
    """node:test tests in a file: `test(...)`, `it(...)` (also `.skip`, `.todo`, `.only`) and subtests `t.test(...)`."""
    return len(_TEST_CALL.findall(_strip(text)))


def js_imports(text: str) -> list[str]:
    """Every module a test file loads with `require(...)`, `import ... from` or `import(...)`."""
    code = _strip(text, keep_strings=True)
    found = re.findall(r"\brequire\s*\(\s*([\"'])(.+?)\1\s*\)", code)
    found += re.findall(r"\bimport\s+(?:[^'\";]+?\s+from\s+)?([\"'])(.+?)\1", code)
    found += re.findall(r"\bimport\s*\(\s*([\"'])(.+?)\1\s*\)", code)
    return sorted({name for _, name in found})


def packages(text: str) -> list[str]:
    """Imports that are neither Node's own modules nor project files: npm packages, which Wings does not install."""
    return [m for m in js_imports(text) if not m.startswith((".", "/", "node:")) and m not in CORE_MODULES]


# TAP as written by `node --test --test-reporter=tap`.
_POINT = re.compile(r"^(?P<indent> *)(?P<ok>not ok|ok) \d+(?: - (?P<name>.*?))?(?: # (?P<directive>SKIP|TODO)\b ?(?P<reason>.*))?$")
_LOCATION = re.compile(r"(?:file:///?)?(?P<path>(?:[A-Za-z]:)?[^\s()'\"]*?\.(?:js|mjs|cjs)):(?P<line>\d+)(?::\d+)?")
_ERROR_LINE = re.compile(r"^\w*(?:Error|Exception)\b.*:|^\w*Error$")


class _Point:
    def __init__(self, name: str, ok: bool, directive: str, reason: str, depth: int):
        self.name, self.ok, self.directive, self.reason, self.depth = name, ok, directive, reason, depth
        self.fields: dict[str, str] = {}
        self.children: list["_Point"] = []
        self.comments: list[str] = []  # diagnostics printed before a top-level point (the file's stderr)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return "" if value == "~" else value


def _yaml(lines: list[str], start: int, indent: int) -> tuple[dict[str, str], int]:
    """The YAML block after a test point (between `---` and `...`): flat keys, `|-` blocks joined by newlines."""
    fields: dict[str, str] = {}
    i = start
    pad = " " * indent
    while i < len(lines) and lines[i].rstrip() != pad + "...":
        m = re.match(rf"^{pad}(\w+):\s?(.*)$", lines[i])
        i += 1
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if value in ("|-", "|", ">-", ">"):
            block: list[str] = []
            while i < len(lines) and (lines[i].startswith(pad + "  ") or not lines[i].strip()) and lines[i].rstrip() != pad + "...":
                block.append(lines[i][len(pad) + 2 :])
                i += 1
            fields[key] = "\n".join(block).strip("\n")
        else:
            fields[key] = _unquote(value)
    return fields, i + 1


def _project_path(raw: str, files: dict[str, str]) -> str | None:
    """A path from Node's output (absolute, in the run folder) as the project path it ends with."""
    norm = re.sub(r"\\+", "/", raw)
    matches = [p for p in files if norm == p or norm.endswith("/" + p)]
    return max(matches, key=len) if matches else None


def _frames(texts: list[str], files: dict[str, str]) -> list[Frame]:
    """Project lines named in stack text, innermost first in the text; returned innermost last."""
    found: list[Frame] = []
    for text in texts:
        for m in _LOCATION.finditer(text):
            path = _project_path(m.group("path"), files)
            if path is None:
                continue
            line = int(m.group("line"))
            lines = files[path].splitlines()
            frame = Frame(path=path, line=line, code=lines[line - 1].strip() if 0 < line <= len(lines) else "")
            if not found or found[-1] != frame:
                found.append(frame)
    return list(reversed(found))[-MAX_FRAMES:]


def _tree(text: str) -> list[_Point]:
    lines = text.splitlines()
    pending: dict[int, list[_Point]] = {}
    comments: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        stripped = line.strip()
        if stripped.startswith("#"):
            body = stripped[1:].strip()
            if not body.startswith("Subtest:"):
                comments.append(body)
            continue
        m = _POINT.match(line)
        if not m:
            continue
        depth = len(m.group("indent")) // 4
        name = (m.group("name") or "").replace("\\#", "#").replace("\\\\", "\\")
        point = _Point(name, m.group("ok") == "ok", m.group("directive") or "", (m.group("reason") or "").strip(), depth)
        point.children = pending.pop(depth + 1, [])
        if depth == 0:
            point.comments, comments = comments, []
        if i < len(lines) and lines[i].strip() == "---":
            point.fields, i = _yaml(lines, i + 1, len(m.group("indent")) + 2)
        pending.setdefault(depth, []).append(point)
    return pending.get(0, [])


def _message(fields: dict[str, str]) -> str:
    return fields.get("error", "").strip()[:2000]


def _first_error(lines: list[str]) -> str:
    for line in lines:
        if _ERROR_LINE.match(line.strip()):
            return line.strip()[:2000]
    return ""


def _leaf(point: _Point, names: list[str], test_path: str, files: dict[str, str]) -> TestResult:
    name = " > ".join([*names, point.name]) or test_path
    outcome: Outcome
    message = ""
    where: list[Frame] = []
    if point.directive:  # SKIP, or TODO (a todo test never fails the run)
        outcome, message = "skipped", point.reason or point.directive.lower()
    elif point.ok:
        outcome = "passed"
    else:
        kind = point.fields.get("failureType", "")
        outcome = "failed" if kind in ("testCodeFailure", "") else "error"
        message = _message(point.fields) or kind
        where = _frames([point.fields.get("stack", "")], files) or _frames([point.fields.get("location", "")], files)
    return TestResult(name=name, classname=test_path, outcome=outcome, message=message, path=test_path, where=where, runner="node")


def _results(point: _Point, names: list[str], test_path: str, files: dict[str, str]) -> list[TestResult]:
    if not point.children:
        if point.fields.get("type") == "suite":
            return []  # an empty describe block
        return [_leaf(point, names, test_path, files)]
    found = [r for child in point.children for r in _results(child, [*names, point.name], test_path, files)]
    if not point.ok and not point.directive and point.fields.get("failureType") != "subtestsFailed":
        # the block failed on its own (a before/after hook): one error under the block's name
        found.append(_leaf(point, names, test_path, files).model_copy(update={"outcome": "error"}))
    return found


def parse_tap(text: str, test_path: str, files: dict[str, str], exit_code: int, output: str = "", timed_out: bool = False, limit: float = 0.0) -> list[TestResult]:
    """The results of one Node run of `test_path`. `files` are the files that ran (path -> source), so a
    failure is shown only with lines in the project. A run that produced no test (it could not start, a
    file that cannot be loaded, the time limit) is one error named after the file, never a pass."""

    def file_error(message: str, where: list[Frame] | None = None) -> TestResult:
        return TestResult(name=test_path, classname=test_path, outcome="error", message=message[:2000], path=test_path, where=where or [], runner="node")

    roots = _tree(text)
    results: list[TestResult] = []
    for point in roots:
        loaded = re.sub(r"\\+", "/", point.name) == test_path
        if loaded and not point.children and not point.ok:
            # Node names the file itself when it could not load it or the file's process failed.
            message = _first_error(point.comments) or _message(point.fields) or "The test file could not be run."
            results.append(file_error(message, _frames(point.comments, files) or _frames([point.fields.get("location", "")], files)))
            continue
        results.extend(_results(point, [], test_path, files))
    if timed_out:
        why = f"Did not finish within {limit:g} s; Node reports a file's tests when the file ends, so later results of this file are lost."
        results.append(file_error(why))
    elif not results:
        if exit_code == 0 and "TAP version" in text:
            results.append(TestResult(name=test_path, classname=test_path, outcome="skipped", message="No tests in this file.", path=test_path, runner="node"))
        else:
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            hint = next((line for line in lines if re.search(r"error|bad option|not found|cannot", line, re.IGNORECASE)), lines[-1] if lines else "")
            results.append(file_error(f"Node could not run this file (exit code {exit_code}). {hint}".strip()))
    return results
