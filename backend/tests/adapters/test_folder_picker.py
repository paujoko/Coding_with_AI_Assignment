"""The folder dialog adapter, without opening a real dialog (the child process is replaced)."""

import os
import subprocess

import pytest

from wings.adapters.folder_picker import NativeFolderPicker
from wings.domain.errors import InvalidInputError


def answering(stdout: str, stderr: str = ""):
    calls = []

    def run(argv, timeout):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=stderr)

    return run, calls


def test_the_chosen_folder_comes_back_as_a_native_path():
    run, calls = answering("PICKED:/home/ben/Projects/todo\n")
    # Tk answers with forward slashes everywhere; the adapter turns that into the platform's own form.
    assert NativeFolderPicker(runner=run, python="py").pick("/home/ben", "Choose") == os.path.normpath("/home/ben/Projects/todo")
    assert calls[0][0] == "py" and calls[0][-2:] == ["/home/ben", "Choose"]


def test_cancel_and_no_answer_are_none():
    run, _ = answering("PICKED:\n")
    assert NativeFolderPicker(runner=run).pick() is None

    def slow(argv, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)

    assert NativeFolderPicker(runner=slow).pick() is None


@pytest.mark.parametrize("stdout, stderr, words", [("NO_TK\n", "", "no Tkinter"), ("", "_tkinter.TclError: no display name", "no display name")])
def test_no_dialog_possible_says_to_type_the_path(stdout, stderr, words):
    run, _ = answering(stdout, stderr)
    with pytest.raises(InvalidInputError, match=words):
        NativeFolderPicker(runner=run).pick()
