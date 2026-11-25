"""Run generated code: a fresh temporary folder per run, a time limit, a reduced environment.

This is a local process, not a container: the code runs with the developer's user rights.
"{python}" in the command is Wings' own interpreter, "{node}" the node on the PATH (JavaScript tests,
ADR 0020); a program that is not there comes back as `not_found`, never as a run.
What it does: the child gets only the variables a Python program needs (no API keys in its
environment), no standard input (so it cannot read the MCP server's stdio or wait for typing),
everything it started is stopped at the time limit (POSIX: its process group; Windows: a job
object that every child joins automatically, with `taskkill /T` as a second line), and its output
is capped. What it cannot
do: stop the code from reading files the user can read (for example `.env`, or another
process's environment through /proc) or from using the network. See ADR 0013. A container-based
sandbox can replace this adapter behind the same port.
"""

import ctypes
import os
import shutil
import signal
import socket
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


class _WindowsJob:
    """A Windows job object: every process the program starts joins it, so ending the job ends them all.

    `taskkill /T` alone walks the tree once and misses a child started a moment later (seen on a loaded
    machine: the grandchild survived the time limit). The job has no such gap. If the job cannot be
    created or joined, `ok` is False and the caller is left with `taskkill`."""

    _KILL_ON_CLOSE = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    _EXTENDED_LIMITS = 9  # JobObjectExtendedLimitInformation

    def __init__(self, proc: subprocess.Popen[bytes]):
        self.ok = False
        self._handle: int | None = None
        try:
            from ctypes import wintypes

            class Basic(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class Extended(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", Basic),
                    ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
            k32.CreateJobObjectW.restype = wintypes.HANDLE
            k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            self._k32 = k32
            handle = k32.CreateJobObjectW(None, None)
            if not handle:
                return
            self._handle = handle
            info = Extended()
            info.BasicLimitInformation.LimitFlags = self._KILL_ON_CLOSE
            configured = k32.SetInformationJobObject(handle, self._EXTENDED_LIMITS, ctypes.byref(info), ctypes.sizeof(info))
            self.ok = bool(configured and k32.AssignProcessToJobObject(handle, int(proc._handle)))  # type: ignore[attr-defined]
        except (OSError, AttributeError, ValueError):
            self.ok = False

    def close(self) -> None:
        """End every process still in the job and release it."""
        if self._handle is None:
            return
        try:
            self._k32.TerminateJobObject(self._handle, 1)
            deadline = time.monotonic() + 2.0  # ending is not instant; a dying process still holds its folder
            while self._active() > 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            self._k32.CloseHandle(self._handle)
        except OSError:
            pass
        self._handle = None

    def _active(self) -> int:
        """How many processes of the job are still alive (0 if that cannot be asked)."""
        counts = (ctypes.c_uint32 * 12)()  # JOBOBJECT_BASIC_ACCOUNTING_INFORMATION: four 64-bit times, then four counters
        if not self._k32.QueryInformationJobObject(self._handle, 1, ctypes.byref(counts), ctypes.sizeof(counts), None):
            return 0
        return int(counts[10])  # ActiveProcesses


def _stop(proc: subprocess.Popen[bytes], job: _WindowsJob | None = None) -> None:
    """Stop the program and everything it started."""
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
    except (OSError, ProcessLookupError):
        pass
    if job is not None:
        job.close()
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait()


def _release(log: Path) -> None:
    """Windows: a program that was just stopped holds its output file for a moment longer. Wait for it
    (at most a second), so the temporary folders can be removed; what is still held then is left behind."""
    deadline = time.monotonic() + 1.0
    while True:
        try:
            log.unlink(missing_ok=True)
            return
        except OSError:
            if time.monotonic() >= deadline:
                return
            time.sleep(0.02)


def _tail(path: Path) -> str:
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > MAX_OUTPUT_BYTES:
            f.seek(size - MAX_OUTPUT_BYTES)
        return f.read().decode("utf-8", errors="replace")


class LocalSandbox:
    def port_in_use(self, port: int) -> bool:
        """A connect, not a bind: on Windows a server with SO_REUSEADDR (Python's `http.server` sets it) can bind
        a port another program listens on, so only a connection says whether the browser would reach someone."""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            return False

    def run(
        self, files: dict[str, str], argv: list[str], timeout: float = 60.0, collect: list[str] | None = None, stdin: str | None = None
    ) -> ProcessResult:
        bad = [f for f in files if not _safe(f)]
        if bad:
            return ProcessResult(exit_code=2, output=f"Refused unsafe path(s): {', '.join(bad)}", seconds=0.0)
        with tempfile.TemporaryDirectory(prefix="wings-run-", ignore_cleanup_errors=True) as tmp, tempfile.TemporaryDirectory(prefix="wings-out-", ignore_cleanup_errors=True) as out_dir:
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
            node = (shutil.which("node", path=env.get("PATH")) or "") if "{node}" in argv else ""
            if "{node}" in argv and not node:
                return ProcessResult(exit_code=127, output="node not found on the PATH", seconds=0.0, not_found=True)
            cmd = [sys.executable if a == "{python}" else node if a == "{node}" else a for a in argv]
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
                    return ProcessResult(exit_code=127, output=f"Could not start {cmd[0]}: {err}", seconds=0.0, not_found=True)
                job = _WindowsJob(proc) if os.name == "nt" else None
                try:
                    code = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    _stop(proc, job)
                    code, timed_out = 124, True
                else:  # children left behind by a program that finished
                    if os.name == "posix":
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except (OSError, ProcessLookupError):
                            pass
                    elif job is not None:
                        job.close()
            seconds = time.perf_counter() - started
            out = _tail(log) + (f"\nStopped after {timeout:.0f} s." if timed_out else "")
            collected = {}
            for rel in collect or []:
                path = root / rel
                if _safe(rel) and path.is_file():
                    collected[rel] = path.read_text(encoding="utf-8", errors="replace")
            _release(log)
        return ProcessResult(exit_code=code, output=out[-MAX_OUTPUT:], seconds=round(seconds, 2), collected=collected, timed_out=timed_out)
