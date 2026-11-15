"""The operating system's folder dialog (Explorer on Windows, Finder on macOS), for the FolderPicker port.

The dialog runs in a short child process with Tkinter (part of the Python installers for Windows and
macOS), not in the server's own threads: Tk wants its own main thread, and a child process can be
stopped cleanly when nobody answers. The window is put on top, so it does not open behind the browser.
"""

import os
import subprocess
import sys
from collections.abc import Callable

from wings.domain.errors import InvalidInputError

TIMEOUT_SECONDS = 600

SCRIPT = r"""
import sys
try:
    import tkinter
    from tkinter import filedialog
except ImportError:
    print("NO_TK")
    raise SystemExit(0)
root = tkinter.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.update()
chosen = filedialog.askdirectory(parent=root, initialdir=sys.argv[1] or None, title=sys.argv[2], mustexist=False)
root.destroy()
print("PICKED:" + (chosen or ""))
"""

Runner = Callable[[list[str], int], subprocess.CompletedProcess[str]]


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, encoding="utf-8")


class NativeFolderPicker:
    def __init__(self, runner: Runner | None = None, python: str | None = None):
        self._run = runner or _run
        self._python = python or sys.executable

    def pick(self, start: str | None = None, title: str = "Choose a folder") -> str | None:
        try:
            done = self._run([self._python, "-c", SCRIPT, start or "", title], TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return None  # nobody answered the dialog
        except OSError as err:
            raise InvalidInputError(f"The folder dialog could not be opened ({err}). Type or paste the path instead.") from err
        out = (done.stdout or "").strip().splitlines()
        last = out[-1] if out else ""
        if last == "NO_TK":
            raise InvalidInputError("This Python has no Tkinter, so Wings cannot open the folder dialog. Type or paste the path instead.")
        if not last.startswith("PICKED:"):
            reason = (done.stderr or "").strip().splitlines()
            hint = f" ({reason[-1]})" if reason else ""
            raise InvalidInputError(f"The folder dialog could not be opened{hint}. Type or paste the path instead.")
        chosen = last.removeprefix("PICKED:").strip()
        return os.path.normpath(chosen) if chosen else None  # Tk answers C:/x/y on Windows
