import json

from wings.domain.testreport import Frame, describe_failures, parse_events, parse_junit

XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3" failures="1" errors="0" skipped="0">
<testcase classname="tests.test_tasks" name="test_req_001_add_task" time="0.01"/>
<testcase classname="tests.test_tasks" name="test_req_003_complete_missing_task" time="0.01">
  <failure message="AssertionError: assert 1 == 0">long traceback</failure>
</testcase>
<testcase classname="tests.test_tasks" name="test_helper_formats_dates" time="0.01"/>
</testsuite></testsuites>"""


def test_junit_results_and_requirement_ids_from_test_names():
    report = parse_junit(XML)
    assert (report.passed, report.failed, report.errors) == (2, 1, 0)
    failed = next(t for t in report.tests if t.outcome == "failed")
    assert failed.requirement == "REQ-003" and "assert 1 == 0" in failed.message
    assert report.by_requirement() == {"REQ-001": "passed", "REQ-003": "failed"}


def test_broken_xml_is_an_error_report():
    report = parse_junit("not xml")
    assert report.errors == 1 and report.tests == []


# Real run (s03): the requirements asked for a browser game, the code was a terminal program, the
# tester said REQ-015 could only partly be tested, and Wings still showed REQ-015 as verified.


def test_declared_gaps_keep_a_requirement_from_counting_as_verified():
    from wings.domain.testreport import Gap, apply_gaps

    verified = {"REQ-001": "passed", "REQ-013": "passed", "REQ-015": "passed", "REQ-002": "failed"}
    code = [Gap(requirement="REQ-015", reason="terminal instead of browser")]
    tests = [Gap(requirement="REQ-013", reason="no DOM to measure"), Gap(requirement="REQ-002", reason="partly")]
    result = apply_gaps(verified, code_gaps=code, test_gaps=tests)
    assert result == {"REQ-001": "passed", "REQ-013": "partial", "REQ-015": "not_met", "REQ-002": "failed"}
    # a code gap is shown even when no test names the requirement
    assert apply_gaps({}, code_gaps=code, test_gaps=[]) == {"REQ-015": "not_met"}


# Real run 2026-11-25 (expense tracker): the run hit the 120 s limit, no JUnit file was written, and the
# debugger only saw "..F...F" and "pytest could not run the tests". The events written while pytest runs
# give each result its file and line, and survive a stopped run.

FILES = {
    "tests/test_calc.py": "from app.calc import add\n\n\ndef test_req_001_adds():\n    assert add(1, 1) == 2\n\n\ndef test_req_002_waits():\n    pass\n",
    "app/calc.py": "def add(a, b):\n    return a - b\n",
}
ADDS = "tests/test_calc.py::test_req_001_adds"
WAITS = "tests/test_calc.py::test_req_002_waits"


def events(*items: dict) -> str:
    return "\n".join(json.dumps(i) for i in items)


def test_a_failure_gets_its_file_line_and_code_in_the_project_only():
    text = events(
        {"event": "start", "nodeid": ADDS},
        {"event": "report", "nodeid": ADDS, "when": "setup", "outcome": "passed"},
        {
            "event": "report",
            "nodeid": ADDS,
            "when": "call",
            "outcome": "failed",
            "message": "assert 0 == 2",
            "frames": [{"path": "tests\\test_calc.py", "line": 5}, {"path": "C:/Python312/Lib/x.py", "line": 9}, {"path": "app/calc.py", "line": 2}],
        },
        {"event": "start", "nodeid": WAITS},
        {"event": "report", "nodeid": WAITS, "when": "call", "outcome": "passed"},
    )
    report = parse_events(text, FILES)
    assert report is not None and (report.passed, report.failed, report.errors) == (1, 1, 0)
    failed = report.tests[0]
    assert (failed.name, failed.classname, failed.path, failed.outcome, failed.message) == ("test_req_001_adds", "tests.test_calc", "tests/test_calc.py", "failed", "assert 0 == 2")
    assert failed.where == [Frame(path="tests/test_calc.py", line=5, code="assert add(1, 1) == 2"), Frame(path="app/calc.py", line=2, code="return a - b")]


def test_a_file_that_cannot_be_collected_is_an_error_with_its_line_from_the_traceback_text():
    text = events(
        {
            "event": "collect",
            "nodeid": "tests/test_calc.py",
            "outcome": "failed",
            "text": "ImportError while importing test module.\nTraceback:\ntests\\test_calc.py:1: in <module>\n    from app.calc import add\nE   ImportError: cannot import name 'add' from 'app.calc'",
        }
    )
    report = parse_events(text, FILES)
    assert report is not None and report.errors == 1 and not report.green
    [broken] = report.tests
    assert (broken.name, broken.outcome) == ("tests/test_calc.py", "error")
    assert broken.message == "ImportError: cannot import name 'add' from 'app.calc'"
    assert broken.where == [Frame(path="tests/test_calc.py", line=1, code="from app.calc import add")]


def test_a_test_that_did_not_finish_is_an_error_pointing_at_the_test():
    text = events({"event": "start", "nodeid": ADDS}, {"event": "report", "nodeid": ADDS, "when": "call", "outcome": "passed"}, {"event": "start", "nodeid": WAITS})
    slow = parse_events(text + "\n" + json.dumps({"event": "slow", "nodeid": WAITS, "seconds": 30}), FILES)
    assert slow is not None and slow.errors == 1 and slow.passed == 1
    hung = slow.tests[1]
    assert hung.outcome == "error" and "30 s" in hung.message and "later tests did not run" in hung.message
    assert hung.where == [Frame(path="tests/test_calc.py", line=8, code="def test_req_002_waits():")]
    stopped = parse_events(text + '\n{"event": "rep', FILES, timed_out=True)  # a line cut off by the stop is skipped
    assert stopped is not None and "time limit" in stopped.tests[1].message


def test_a_stopped_run_is_never_green_even_when_every_started_test_finished():
    text = events({"event": "start", "nodeid": ADDS}, {"event": "report", "nodeid": ADDS, "when": "call", "outcome": "passed"})
    assert parse_events(text, FILES).green  # type: ignore[union-attr]
    assert not parse_events(text, FILES, timed_out=True).green  # type: ignore[union-attr]


def test_setup_and_teardown_failures_are_errors_and_skips_stay_skips():
    text = events(
        {"event": "start", "nodeid": ADDS},
        {"event": "report", "nodeid": ADDS, "when": "setup", "outcome": "failed", "message": "fixture 'db' not found"},
        {"event": "start", "nodeid": WAITS},
        {"event": "report", "nodeid": WAITS, "when": "setup", "outcome": "skipped", "message": "Skipped: later"},
    )
    report = parse_events(text, FILES)
    assert report is not None and [(t.outcome, t.message) for t in report.tests] == [("error", "fixture 'db' not found"), ("skipped", "Skipped: later")]


def test_no_events_means_the_caller_falls_back_to_junit():
    assert parse_events("", FILES) is None
    assert parse_events("not json", FILES) is None


def test_failures_are_described_with_their_lines_for_an_agent():
    report = parse_events(
        events(
            {"event": "start", "nodeid": ADDS},
            {"event": "report", "nodeid": ADDS, "when": "call", "outcome": "failed", "message": "assert 0 == 2\nmore", "frames": [{"path": "tests/test_calc.py", "line": 5}, {"path": "app/calc.py", "line": 2}]},
        ),
        FILES,
    )
    text = describe_failures(report.tests)  # type: ignore[union-attr]
    assert "1. test_req_001_adds (tests/test_calc.py): failed" in text
    assert "assert 0 == 2" in text and "more" not in text
    assert "tests/test_calc.py:5  assert add(1, 1) == 2" in text and "app/calc.py:2  return a - b" in text


# Real run 2026-11-25 (Flappy Bird): 49 green tests, but only REQ-001 of 19 had a passing test, and Testing
# could be approved as if everything was checked. The count of verified requirements is computed by code.


def test_requirement_ids_in_test_names_may_use_a_dash():
    from wings.domain.testreport import TestResult

    assert TestResult(name="REQ-007 bird falls", outcome="passed").requirement == "REQ-007"
    assert TestResult(name="test_req_007_bird_falls", outcome="passed").requirement == "REQ-007"
    assert TestResult(name="req007", outcome="passed").requirement == "REQ-007"


def test_verification_counts_every_requirement_including_those_without_a_test():
    from wings.domain.testreport import verification

    ids = [f"REQ-{i:03d}" for i in range(1, 20)]
    verdicts = {"REQ-001": "passed", "REQ-002": "passed", "REQ-003": "passed", "REQ-004": "partial", "REQ-005": "not_met", "REQ-006": "failed", "REQ-007": "error", "REQ-008": "skipped", "REQ-099": "passed"}
    v = verification(ids, verdicts)
    assert v.total == 19 and v.verified == ["REQ-001", "REQ-002", "REQ-003"]
    assert v.partial == ["REQ-004"] and v.not_met == ["REQ-005"] and v.failing == ["REQ-006", "REQ-007"] and v.skipped == ["REQ-008"]
    assert v.no_result == [f"REQ-{i:03d}" for i in range(9, 20)]
    assert v.summary == (
        "3 of 19 requirements verified by a passing test; 11 without a test result; 1 only partly tested; "
        "1 not met by the code; 2 with failing tests; 1 with skipped tests only."
    )


def test_verification_sentence_when_everything_is_verified_or_nothing_is_defined():
    from wings.domain.testreport import verification

    assert verification(["REQ-001", "REQ-002"], {"REQ-001": "passed", "REQ-002": "passed"}).summary == "2 of 2 requirements verified by a passing test."
    assert verification(["REQ-001"], {}).summary == "0 of 1 requirement verified by a passing test; 1 without a test result."
    assert verification([], {"REQ-001": "passed"}).summary == "No requirements to verify."
