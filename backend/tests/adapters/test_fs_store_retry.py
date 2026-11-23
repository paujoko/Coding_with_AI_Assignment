"""The store survives the short moments in which Windows refuses a read or a rename (real 500, 2026-11-23)."""

import os
import threading
from pathlib import Path

import pytest

from wings.adapters import fs_store
from wings.adapters.fs_store import FileSystemStore, _retrying
from wings.domain.phases import PhaseId
from wings.domain.project import Project


def _project() -> Project:
    return Project.new("Demo", {PhaseId.REQUIREMENTS: []}, project_id="demo")


def test_an_operation_that_fails_a_few_times_is_tried_again():
    calls, naps = [], []

    def flaky() -> str:
        calls.append(1)
        if len(calls) <= 3:
            raise PermissionError(13, "Permission denied")
        return "done"

    assert _retrying(flaky, seconds=5, sleep=naps.append) == "done"
    assert len(calls) == 4 and len(naps) == 3


def test_a_lasting_permission_problem_is_raised_after_the_time_limit():
    calls = []

    def locked() -> None:
        calls.append(1)
        raise PermissionError(13, "Permission denied")

    with pytest.raises(PermissionError):
        _retrying(locked, seconds=0.05)
    assert len(calls) > 1


def test_other_errors_are_not_retried():
    calls = []

    def missing() -> None:
        calls.append(1)
        raise FileNotFoundError("gone")

    with pytest.raises(FileNotFoundError):
        _retrying(missing, seconds=5)
    assert len(calls) == 1


def test_loading_a_project_waits_for_a_writer_to_let_go(tmp_path, monkeypatch):
    store = FileSystemStore(tmp_path)
    store.save_project(_project())
    real, failures = Path.read_text, [2]

    def read_text(self: Path, *args, **kwargs) -> str:
        if self.name == "project.json" and failures[0] > 0:
            failures[0] -= 1
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert store.load_project("demo").name == "Demo"
    assert failures[0] == 0


def test_saving_waits_for_a_reader_to_let_go(tmp_path, monkeypatch):
    store = FileSystemStore(tmp_path)
    project = _project()
    store.save_project(project)
    real, failures = os.replace, [2]

    def replace(src, dst) -> None:
        if failures[0] > 0:
            failures[0] -= 1
            raise PermissionError(13, "Access is denied", str(dst))
        real(src, dst)

    monkeypatch.setattr(fs_store.os, "replace", replace)
    store.save_project(project)
    assert failures[0] == 0 and store.load_project("demo").version == 2


def test_readers_and_a_writer_at_the_same_time_never_fail(tmp_path):
    """Hammer: one thread saves the project again and again while others load it (GET /events during an action)."""
    store = FileSystemStore(tmp_path)
    project = _project()
    store.save_project(project)
    errors: list[BaseException] = []
    stop = threading.Event()

    def read() -> None:
        while not stop.is_set():
            try:
                store.load_project("demo")
                store.list_projects()
            except BaseException as err:  # noqa: BLE001 - the test reports whatever went wrong
                errors.append(err)
                return

    readers = [threading.Thread(target=read) for _ in range(4)]
    for t in readers:
        t.start()
    try:
        for _ in range(300):
            store.save_project(project)
    except BaseException as err:  # noqa: BLE001
        errors.append(err)
    finally:
        stop.set()
        for t in readers:
            t.join()
    assert errors == []
    assert store.load_project("demo").version == 301
