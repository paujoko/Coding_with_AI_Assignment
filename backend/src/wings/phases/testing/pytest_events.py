"""Copied into every test run as `_wings_events.py` and loaded with `-p _wings_events`. Never imported by Wings.

Writes one JSON line per event to `_wings_events.jsonl` while pytest runs, flushed at once, so the
results survive a run that is stopped. A failure carries its traceback lines (file and line). With
`--wings-test-limit=N`, a test that runs longer than N seconds ends the run: the event names it.
Standard library only; it runs inside the developer's project.
"""

import json
import os
import threading

_OUT = "_wings_events.jsonl"
_ROOT = os.getcwd()
_lock = threading.Lock()
_state: dict = {"limit": 0.0, "timer": None}


def _write(event: dict) -> None:
    with _lock, open(os.path.join(_ROOT, _OUT), "a", encoding="utf-8") as sink:
        sink.write(json.dumps(event) + "\n")


def _clean(text: str) -> str:
    return text.replace(_ROOT + os.sep, "").replace(_ROOT, "")


def _details(longrepr) -> dict:
    if longrepr is None:
        return {}
    if isinstance(longrepr, tuple):  # a skip: (file, line, reason)
        return {"message": str(longrepr[-1])}
    frames = []
    traceback = getattr(longrepr, "reprtraceback", None)
    for entry in getattr(traceback, "reprentries", None) or []:
        loc = getattr(entry, "reprfileloc", None)
        if loc is not None:
            frames.append({"path": _clean(str(loc.path)), "line": int(loc.lineno)})
    crash = getattr(longrepr, "reprcrash", None)
    if crash is not None and not frames:
        frames.append({"path": _clean(str(crash.path)), "line": int(crash.lineno)})
    return {"message": _clean(str(getattr(crash, "message", "") or "")), "frames": frames, "text": _clean(str(longrepr))[-4000:]}


def pytest_addoption(parser) -> None:
    parser.addoption("--wings-test-limit", type=float, default=0.0, help="End the run when one test takes longer (seconds)")


def pytest_configure(config) -> None:
    _state["limit"] = config.getoption("--wings-test-limit")
    open(os.path.join(_ROOT, _OUT), "w", encoding="utf-8").close()


def pytest_collectreport(report) -> None:
    if report.failed:
        _write({"event": "collect", "nodeid": report.nodeid, "outcome": "failed", **_details(report.longrepr)})


def pytest_runtest_logstart(nodeid, location) -> None:
    _write({"event": "start", "nodeid": nodeid})
    limit = _state["limit"]
    if limit > 0:

        def stop() -> None:
            _write({"event": "slow", "nodeid": nodeid, "seconds": limit})
            os._exit(3)

        timer = threading.Timer(limit, stop)
        timer.daemon = True
        timer.start()
        _state["timer"] = timer


def pytest_runtest_logfinish(nodeid, location) -> None:
    timer = _state.pop("timer", None)
    if timer is not None:
        timer.cancel()


def pytest_runtest_logreport(report) -> None:
    event = {"event": "report", "nodeid": report.nodeid, "when": report.when, "outcome": report.outcome}
    if report.outcome != "passed":
        event.update(_details(report.longrepr))
    _write(event)
