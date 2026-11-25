"""JavaScript tests (ADR 0020): Node's TAP output read into results, importable files, test counts.

The TAP samples are real output of `node --test --test-reporter=tap` (Node 24.12, Windows), shortened.
Real run 2026-11-25 (Flappy Bird): all game logic was in game.js, Wings ran only pytest, and 12 of 19
requirements had no test result at all.
"""

from wings.domain.nodetest import count_js_tests, is_js_source, is_js_test, js_exports, js_imports, parse_tap

FILES = {
    "tests/logic.test.js": "const test = require('node:test');\n" * 20,
    "game/static/logic.js": "function add(a, b) {\n  return a - b;\n}\n" + "\n" * 20,
    "game/static/page.js": 'document.getElementById("x").textContent = "hi";\n',
    "tests/page.test.js": "require('../game/static/page.js');\n",
}
ROOT = "C:\\\\Users\\\\me\\\\AppData\\\\Local\\\\Temp\\\\wings-run-abc"
STACK_ROOT = "C:\\Users\\me\\AppData\\Local\\Temp\\wings-run-abc"

TAP = f"""TAP version 13
# Subtest: REQ-001 adds two numbers
ok 1 - REQ-001 adds two numbers
  ---
  duration_ms: 0.8889
  type: 'test'
  ...
# Subtest: req_002 fails on purpose
not ok 2 - req_002 fails on purpose
  ---
  duration_ms: 0.8283
  type: 'test'
  location: '{ROOT}\\\\tests\\\\logic.test.js:9:1'
  failureType: 'testCodeFailure'
  error: |-
    Expected values to be strictly equal:

    3 !== 4

  code: 'ERR_ASSERTION'
  stack: |-
    add ({STACK_ROOT}\\game\\static\\logic.js:2:3)
    TestContext.<anonymous> ({STACK_ROOT}\\tests\\logic.test.js:10:10)
    Test.runInAsyncScope (node:async_hooks:214:14)
  ...
# Subtest: REQ-003 bird
    # Subtest: falls
    ok 1 - falls
      ---
      duration_ms: 0.3069
      type: 'test'
      ...
    # Subtest: skipped one
    ok 2 - skipped one # SKIP not yet
      ---
      duration_ms: 0.1373
      type: 'test'
      ...
    # Subtest: times out
    not ok 3 - times out
      ---
      duration_ms: 30001
      type: 'test'
      location: '{ROOT}\\\\tests\\\\logic.test.js:15:3'
      failureType: 'testTimeoutFailure'
      error: 'test timed out after 30000ms'
      code: 'ERR_TEST_FAILURE'
      ...
    1..3
not ok 3 - REQ-003 bird
  ---
  duration_ms: 0.9112
  type: 'suite'
  location: '{ROOT}\\\\tests\\\\logic.test.js:12:1'
  failureType: 'subtestsFailed'
  error: '1 subtest failed'
  code: 'ERR_TEST_FAILURE'
  ...
# Subtest: todo one
ok 4 - todo one # TODO
  ---
  duration_ms: 0.1544
  type: 'test'
  ...
# Subtest: a \\# in the name
ok 5 - a \\# in the name
  ---
  duration_ms: 0.1
  type: 'test'
  ...
1..5
# tests 6
# pass 3
# fail 2
"""


def by_name(results):
    return {r.name: r for r in results}


def test_tap_results_with_nested_names_outcomes_and_requirements():
    results = parse_tap(TAP, "tests/logic.test.js", FILES, exit_code=1)
    found = by_name(results)
    assert set(found) == {"REQ-001 adds two numbers", "req_002 fails on purpose", "REQ-003 bird > falls", "REQ-003 bird > skipped one", "REQ-003 bird > times out", "todo one", "a # in the name"}
    assert all(r.runner == "node" and r.path == "tests/logic.test.js" for r in results)
    assert found["REQ-001 adds two numbers"].outcome == "passed" and found["REQ-001 adds two numbers"].requirement == "REQ-001"
    # a nested test inherits the requirement of its describe block
    assert found["REQ-003 bird > falls"].requirement == "REQ-003"
    assert found["REQ-003 bird > skipped one"].outcome == "skipped" and "not yet" in found["REQ-003 bird > skipped one"].message
    assert found["todo one"].outcome == "skipped"
    # the suite line itself ("1 subtest failed") is not a test of its own
    assert "REQ-003 bird" not in found


def test_a_failure_carries_its_message_and_the_project_lines_innermost_last():
    failed = by_name(parse_tap(TAP, "tests/logic.test.js", FILES, exit_code=1))["req_002 fails on purpose"]
    assert failed.outcome == "failed" and failed.requirement == "REQ-002"
    assert failed.message.startswith("Expected values to be strictly equal") and "3 !== 4" in failed.message
    assert [(f.path, f.line) for f in failed.where] == [("tests/logic.test.js", 10), ("game/static/logic.js", 2)]
    assert failed.where[-1].code == "return a - b;"


def test_a_test_over_its_time_limit_is_an_error_not_a_failure():
    slow = by_name(parse_tap(TAP, "tests/logic.test.js", FILES, exit_code=1))["REQ-003 bird > times out"]
    assert slow.outcome == "error" and "timed out" in slow.message
    assert [(f.path, f.line) for f in slow.where] == [("tests/logic.test.js", 15)]


PAGE_TAP = f"""TAP version 13
# {ROOT}\\\\game\\\\static\\\\page.js:1
# document.getElementById("x").textContent = "hi";
# ^
# ReferenceError: document is not defined
#     at Object.<anonymous> ({ROOT}\\\\game\\\\static\\\\page.js:1:1)
#     at Module._compile (node:internal/modules/cjs/loader:1761:14)
#     at Object.<anonymous> ({ROOT}\\\\tests\\\\page.test.js:1:1)
# Node.js v24.12.0
# Subtest: tests\\\\page.test.js
not ok 1 - tests\\\\page.test.js
  ---
  duration_ms: 68.8559
  type: 'test'
  location: '{ROOT}\\\\tests\\\\page.test.js:1:1'
  failureType: 'testCodeFailure'
  exitCode: 1
  error: 'test failed'
  code: 'ERR_TEST_FAILURE'
  ...
1..1
"""


def test_a_file_that_cannot_be_loaded_is_one_error_with_the_reason_and_line():
    """A browser script with no exports touches the page when Node loads it (the Flappy Bird case)."""
    [result] = parse_tap(PAGE_TAP, "tests/page.test.js", FILES, exit_code=1)
    assert result.outcome == "error" and result.name == "tests/page.test.js"
    assert result.message == "ReferenceError: document is not defined"
    assert [(f.path, f.line) for f in result.where] == [("tests/page.test.js", 1), ("game/static/page.js", 1)]


def test_a_run_stopped_at_the_time_limit_names_the_file_and_never_passes():
    [result] = parse_tap("TAP version 13\n", "tests/logic.test.js", FILES, exit_code=124, timed_out=True, limit=60)
    assert result.outcome == "error" and "60 s" in result.message and result.path == "tests/logic.test.js"


def test_a_run_with_no_output_is_an_error_with_the_console_line():
    [result] = parse_tap("", "tests/logic.test.js", FILES, exit_code=9, output="node: bad option: --test-force-exit\n")
    assert result.outcome == "error" and "bad option" in result.message


def test_a_file_without_tests_is_reported_as_skipped():
    [result] = parse_tap("TAP version 13\n1..0\n# tests 0\n", "tests/logic.test.js", FILES, exit_code=0)
    assert result.outcome == "skipped" and "no tests" in result.message.lower()


def test_esm_stack_lines_with_file_urls_map_to_project_files():
    tap = """TAP version 13
not ok 1 - REQ-004 esm
  ---
  type: 'test'
  failureType: 'testCodeFailure'
  error: 'boom'
  stack: |-
    file:///C:/tmp/wings-run-x/tests/logic.test.js:3:9
  ...
1..1
"""
    [result] = parse_tap(tap, "tests/logic.test.js", FILES, exit_code=1)
    assert result.outcome == "failed" and result.message == "boom" and [(f.path, f.line) for f in result.where] == [("tests/logic.test.js", 3)]


def test_which_paths_are_javascript_tests_and_sources():
    assert is_js_test("tests/game.test.js") and is_js_test("tests/game.test.mjs") and is_js_test("tests/game.test.cjs")
    assert not is_js_test("tests/test_game.py") and not is_js_test("game/static/game.js")
    assert is_js_source("game/static/game.js") and is_js_source("game/logic.mjs")
    assert not is_js_source("tests/game.test.js") and not is_js_source("game/models.py")


def test_exports_say_whether_node_can_import_a_file():
    guard = 'class Bird {}\nfunction step() {}\nif (typeof module !== "undefined" && module.exports) {\n  module.exports = { Bird, step };\n}\n'
    assert js_exports(guard) == ["Bird", "step"]
    assert js_exports("module.exports.add = add;\nexports.sub = sub;\n") == ["add", "sub"]
    assert js_exports("export function add() {}\nexport class Bird {}\nexport const g = 1;\nexport { a, b as c };\n") == ["Bird", "a", "add", "c", "g"]
    assert js_exports("module.exports = Game;\n") == ["Game"]
    assert js_exports("export default class Game {}\n") == ["default"]
    # a browser script: everything global, nothing for Node to import
    assert js_exports('const canvas = document.getElementById("c");\nfunction loop() {}\n') == []
    # a word in a comment or string is not an export
    assert js_exports('// module.exports = { x }\nconst s = "export function f";\n') == []


def test_counting_node_tests():
    text = """const test = require("node:test");
const { describe, it } = require("node:test");
test("REQ-001 one", () => {});
test('REQ-002 two', async (t) => {
  await t.test("inner", () => {});
});
describe("REQ-003 group", () => {
  it("a", () => {});
  it.skip("b", () => {});
});
// test("commented out", () => {});
"""
    assert count_js_tests(text) == 5


def test_imports_name_packages_and_project_files():
    text = """const test = require("node:test");
const assert = require('node:assert/strict');
const fs = require("fs");
const { Bird } = require("../game/static/logic.js");
import { add } from "../game/static/logic.js";
import chai from "chai";
const jest = require("@jest/globals");
"""
    assert js_imports(text) == ["../game/static/logic.js", "@jest/globals", "chai", "fs", "node:assert/strict", "node:test"]
