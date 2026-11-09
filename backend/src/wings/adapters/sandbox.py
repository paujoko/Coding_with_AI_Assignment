"""Run generated code: a fresh temporary folder per run, a time limit, a clean environment.

This is a local process, not a container: the code runs with the developer's user rights.
The environment carries no API keys or other secrets, and nothing outside the temporary
folder is written by Wings. A Docker-based sandbox can replace this adapter behind the same port.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

from wings.application.ports import ProcessResult

# Variables a Python program needs to start on Windows, macOS and Linux; nothing else is passed on.
_KEEP = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL")
MAX_OUTPUT = 20_000


def _safe(rel: str) -> bool:
    p = PurePosixPath(rel)
    return bool(rel) and "\\" not in rel and not p.is_absolute() and ".." not in p.parts and ":" not in p.parts[0]


class LocalSandbox:
    def run(self, files: dict[str, str], argv: list[str], timeout: float = 60.0, collect: list[str] | None = None) -> ProcessResult:
        bad = [f for f in files if not _safe(f)]
        if bad:
            return ProcessResult(exit_code=2, output=f"Refused unsafe path(s): {', '.join(bad)}", seconds=0.0)
        with tempfile.TemporaryDirectory(prefix="wings-run-") as tmp:
            root = Path(tmp)
            for rel, text in files.items():
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if k in _KEEP}
            env.update({"PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"})
            cmd = [sys.executable if a == "{python}" else a for a in argv]
            started = time.perf_counter()
            try:
                done = subprocess.run(cmd, cwd=root, env=env, capture_output=True, timeout=timeout)
                code, out, timed_out = done.returncode, (done.stdout + done.stderr).decode("utf-8", errors="replace"), False
            except subprocess.TimeoutExpired as err:
                partial = (err.stdout or b"") + (err.stderr or b"")
                code, out, timed_out = 124, partial.decode("utf-8", errors="replace") + f"\nStopped after {timeout:.0f} s.", True
            except OSError as err:
                code, out, timed_out = 127, f"Could not start {cmd[0]}: {err}", False
            seconds = time.perf_counter() - started
            collected = {}
            for rel in collect or []:
                path = root / rel
                if _safe(rel) and path.is_file():
                    collected[rel] = path.read_text(encoding="utf-8", errors="replace")
        return ProcessResult(exit_code=code, output=out[-MAX_OUTPUT:], seconds=round(seconds, 2), collected=collected, timed_out=timed_out)
