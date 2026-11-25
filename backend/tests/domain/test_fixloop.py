"""The fix loop's memory: what each attempt changed and what the next run showed (real run 2026-11-25:
each explanation started from zero, and the time tracker "got lost in the tests")."""

from wings.domain.fixloop import FixLog


def attempt(log: FixLog, failing: list[str], cause: str = "code", changed: list[str] | None = None) -> FixLog:
    return log.attempt(failing=failing, cause=cause, diagnosis=f"Diagnosis for {', '.join(failing)}.", fix="Change the method.", changed=changed or [])


def test_each_attempt_is_remembered_with_what_the_next_run_showed():
    log = attempt(FixLog(), ["test_a", "test_b"], cause="test", changed=["tests/conftest.py"]).after_run(["test_b", "test_c"])
    [first] = log.attempts
    assert (first.number, first.cause, first.changed, first.after) == (1, "test", ["tests/conftest.py"], ["test_b", "test_c"])
    text = log.prompt()
    assert "Attempt 1 (cause: test)" in text and "Changed: tests/conftest.py" in text
    assert "fixed: test_a" in text and "still failing: test_b" in text and "newly failing: test_c" in text
    assert "Do not repeat" in text


def test_an_attempt_without_a_run_after_it_says_so_and_a_second_run_does_not_overwrite_the_first():
    log = attempt(FixLog(), ["test_a"])
    assert "not run again yet" in log.prompt()
    log = log.after_run(["test_a"]).after_run([])
    assert log.attempts[0].after == ["test_a"]


def test_a_test_that_fails_after_every_attempt_is_named_as_stuck():
    log = attempt(attempt(FixLog(), ["test_a", "test_b"]).after_run(["test_a"]), ["test_a"]).after_run(["test_a"])
    assert log.stuck() == ["test_a"]
    assert "test_a still fails after 2 attempts" in log.prompt()
    assert [a.number for a in log.attempts] == [1, 2]


def test_a_run_before_any_attempt_changes_nothing_and_an_empty_log_says_nothing():
    assert FixLog().after_run(["test_a"]).attempts == []
    assert FixLog().prompt() == ""
    assert FixLog().stuck() == []


def test_the_markdown_lists_every_attempt():
    log = attempt(FixLog(), ["test_a"]).after_run([])
    text = log.markdown()
    assert text.startswith("# Fix attempts") and "## Attempt 1 (cause: code)" in text and "After it: all tests pass." in text
