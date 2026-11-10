"""Run generated code: a fresh temporary folder per run, a time limit, a reduced environment.

This is a local process, not a container: the code runs with the developer's user rights.
What it does: the child gets only the variables a Python program needs (no API keys in its
environment), no standard input (so it cannot read the MCP server's stdio or wait for typing),
its whole process group is stopped at the time limit, and its output is capped. What it cannot
do: stop the code from reading files the user can read (for example `.env`, or another
process's environment through /proc) or from using the network. See ADR 0013. A container-based
sandbox can replace this adapter behind the same port.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

from wings.application.ports import ProcessResult

# Variables a Python program needs to start on Windows, macOS and Linux; nothing else is passed on.
_KEEP = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL")
MAX_OUTPUT = 20_000  # characters of output kept (the end)
MAX_OUTPUT_BYTES = 2_000_000  # read at most this much of the output file


def _safe(rel: str) -> bool:
    p = PurePosixPath(rel)
    parts = [x for x in p.parts if x not in (".",)]
    return bool(parts) and "\\" not in rel and not p.is_absolute() and ".." not in p.parts and ":" not in parts[0]


def _stop(proc: subprocess.Popen[bytes]) -> None:
    """Stop the program and everything it started."""
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait()


def _tail(path: Path) -> str:
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > MAX_OUTPUT_BYTES:
            f.seek(size - MAX_OUTPUT_BYTES)
        return f.read().decode("utf-8", errors="replace")


class LocalSandbox:
    def run(
        self, files: dict[str, str], argv: list[str], timeout: float = 60.0, collect: list[str] | None = None, stdin: str | None = None
    ) -> ProcessResult:
        bad = [f for f in files if not _safe(f)]
        if bad:
            return ProcessResult(exit_code=2, output=f"Refused unsafe path(s): {', '.join(bad)}", seconds=0.0)
        with tempfile.TemporaryDirectory(prefix="wings-run-") as tmp, tempfile.TemporaryDirectory(prefix="wings-out-") as out_dir:
            root = Path(tmp)
            try:
                for rel, text in files.items():
                    target = root / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text, encoding="utf-8")
            except OSError as err:  # e.g. "a" as a file and "a/b.py" in the same set
                return ProcessResult(exit_code=2, output=f"Could not write the files: {err}", seconds=0.0)
            env = {k: v for k, v in os.environ.items() if k in _KEEP}
            env.update({"PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"})
            cmd = [sys.executable if a == "{python}" else a for a in argv]
            log = Path(out_dir) / "output.txt"
            given = Path(out_dir) / "stdin.txt"  # input as a file: never the parent's stdin (MCP stdio)
            given.write_text(stdin or "", encoding="utf-8")
            started = time.perf_counter()
            timed_out = False
            with log.open("wb") as sink, given.open("rb") as source:
                try:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=root,
                        env=env,
                        stdin=source if stdin is not None else subprocess.DEVNULL,
                        stdout=sink,
                        stderr=subprocess.STDOUT,
                        start_new_session=os.name == "posix",
                        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                    )
                except OSError as err:
                    return ProcessResult(exit_code=127, output=f"Could not start {cmd[0]}: {err}", seconds=0.0)
                try:
                    code = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    _stop(proc)
                    code, timed_out = 124, True
                else:
                    if os.name == "posix":  # children left behind by a program that finished
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except (OSError, ProcessLookupError):
                            pass
            seconds = time.perf_counter() - started
            out = _tail(log) + (f"\nStopped after {timeout:.0f} s." if timed_out else "")
            collected = {}
            for rel in collect or []:
                path = root / rel
                if _safe(rel) and path.is_file():
                    collected[rel] = path.read_text(encoding="utf-8", errors="replace")
        return ProcessResult(exit_code=code, output=out[-MAX_OUTPUT:], seconds=round(seconds, 2), collected=collected, timed_out=timed_out)
