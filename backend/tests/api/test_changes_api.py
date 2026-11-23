"""HTTP surface of change propagation: GET /changes, POST /changes/{n}/advance, open_change in the project."""

import pytest
from fastapi.testclient import TestClient

from wings.adapters.sandbox import LocalSandbox
from wings.api.app import create_app
from wings.domain.phases import PhaseId as P


@pytest.fixture
def client_and_project(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    orch.sandbox = LocalSandbox()
    pid = walk(orch, P.MAINTENANCE)
    return TestClient(create_app(orch, {"llm_provider": "mock"})), pid


def test_changes_are_listed_and_carried_through_over_http(client_and_project):
    client, pid = client_and_project
    assert client.get(f"/api/projects/{pid}/changes").json() == []
    assert client.get(f"/api/projects/{pid}").json()["open_change"] is None

    asked = client.post(f"/api/projects/{pid}/phases/maintenance/actions/change", json={"input": {"request": "Tasks need a priority"}}).json()
    assert asked["data"]["change"] == 1
    assert asked["project"]["open_change"] == {"number": 1, "done": 0, "total": 6, "next_phase": "requirements"}

    [change] = client.get(f"/api/projects/{pid}/changes").json()
    assert set(change) == {"number", "artifact_id", "kind", "request", "summary", "affected", "state", "started_at", "completed_at", "progress", "next", "receipt"}
    assert change["state"] == "open" and change["next"]["kind"] == "run" and change["next"]["phase"] == "requirements"
    assert change["progress"]["phases"][0] == {"phase": "requirements", "title": "Requirements", "state": "current", "status": "approved", "updated": False}

    step = client.post(f"/api/projects/{pid}/changes/1/advance", json={"approve": True}).json()
    assert set(step) == {"project", "change", "ran", "approved", "stopped_reason"}
    assert step["approved"] == "requirements" and step["stopped_reason"] is None
    assert step["ran"][0]["action"] == "revise" and step["ran"][0]["status"] == "draft"
    assert step["project"]["open_change"] == {"number": 1, "done": 1, "total": 6, "next_phase": "design"}
    assert step["change"]["receipt"][0]["updated"][0]["id"] == "requirements"

    for _ in range(8):
        step = client.post(f"/api/projects/{pid}/changes/1/advance").json()  # no body: approve defaults to true
        if step["stopped_reason"] is not None or step["change"]["state"] != "open":
            break
    assert step["change"]["state"] == "complete" and step["stopped_reason"] is None
    assert step["project"]["open_change"] is None
    assert client.get(f"/api/projects/{pid}").json()["open_change"] is None
    [done] = client.get(f"/api/projects/{pid}/changes").json()
    assert done["completed_at"] and all(len(r["updated"]) + len(r["added"]) + len(r["removed"]) > 0 for r in done["receipt"])


def test_unknown_change_is_404(client_and_project):
    client, pid = client_and_project
    assert client.post(f"/api/projects/{pid}/changes/3/advance").status_code == 404
