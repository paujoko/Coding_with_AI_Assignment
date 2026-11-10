from wings.domain.testreport import parse_junit

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
