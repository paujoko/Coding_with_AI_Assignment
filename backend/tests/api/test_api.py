import pytest
from fastapi.testclient import TestClient

from wings.api.app import create_app


@pytest.fixture
def client(make_orchestrator, demo_script):
    return TestClient(create_app(make_orchestrator(demo_script), {"llm_provider": "mock"}))


def act(client, pid, phase, action, **input):
    return client.post(f"/api/projects/{pid}/phases/{phase}/actions/{action}", json={"input": input})


def test_health_and_phase_catalog(client):
    assert client.get("/api/health").json()["llm_provider"] == "mock"
    phases = client.get("/api/phases").json()
    assert [p["id"] for p in phases][:2] == ["requirements", "design"]
    start = phases[0]["actions"][0]
    assert start["name"] == "start" and "description" in start["input_schema"]["properties"]


def test_requirements_to_design_happy_path(client):
    pid = client.post("/api/projects", json={"name": "Büro Todo"}).json()["id"]
    assert pid == "buero-todo"

    r = act(client, pid, "requirements", "start", description="A todo app")
    assert r.status_code == 200 and r.json()["data"]["questions"]
    r = act(client, pid, "requirements", "answer", answers="CLI")
    assert r.json()["project"]["phases"][0]["status"] == "draft"

    assert client.post(f"/api/projects/{pid}/phases/requirements/approve").json()["phases"][1]["can_run"] is True
    r = act(client, pid, "design", "generate")
    assert r.status_code == 200 and len(r.json()["artifacts"]) == 3

    assert client.get(f"/api/projects/{pid}/trace").json()["uncovered"] == []
    assert len(client.get(f"/api/projects/{pid}/artifacts", params={"phase": "design"}).json()) == 3
    msgs = client.get(f"/api/projects/{pid}/messages", params={"phase": "requirements"}).json()
    assert [m["role"] for m in msgs] == ["developer", "agent", "developer", "agent"]
    seqs = [e["seq"] for e in client.get(f"/api/projects/{pid}/events", params={"after": 3}).json()]
    assert seqs and seqs[0] == 4


def test_errors_map_to_http_codes(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    assert act(client, pid, "design", "generate").status_code == 409  # locked
    assert act(client, pid, "codegen", "anything").status_code == 409  # planned wing
    assert act(client, pid, "requirements", "nope").status_code == 404
    assert act(client, pid, "nonsense", "start").status_code == 404
    assert client.get("/api/projects/missing").status_code == 404
    assert act(client, pid, "requirements", "start").status_code == 422  # description missing
    assert client.post(f"/api/projects/{pid}/phases/requirements/approve").status_code == 409


def test_developer_edit_marks_design_stale(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    act(client, pid, "requirements", "start", description="x")
    act(client, pid, "requirements", "answer", answers="y")
    client.post(f"/api/projects/{pid}/phases/requirements/approve")
    act(client, pid, "design", "generate")
    req = client.get(f"/api/projects/{pid}/artifacts/requirements").json()
    r = client.put(f"/api/projects/{pid}/artifacts/requirements", json={"content": req["content"]})
    assert r.status_code == 200 and r.json()["stale"] == ["design"]
    assert len(client.get(f"/api/projects/{pid}/artifacts/requirements/history").json()) == 2


def test_svg_without_renderer_is_503(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    act(client, pid, "requirements", "start", description="x")
    act(client, pid, "requirements", "answer", answers="y")
    client.post(f"/api/projects/{pid}/phases/requirements/approve")
    act(client, pid, "design", "generate")
    assert client.get(f"/api/projects/{pid}/artifacts/diagram-use-cases/svg").status_code == 503


def test_input_errors_are_422_and_internal_errors_are_not(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    act(client, pid, "requirements", "start", description="x")
    act(client, pid, "requirements", "answer", answers="y")
    client.post(f"/api/projects/{pid}/phases/requirements/approve")
    act(client, pid, "design", "generate")
    bad_edit = client.put(f"/api/projects/{pid}/artifacts/diagram-use-cases", json={"text": "not uml"})
    assert bad_edit.status_code == 422 and bad_edit.json()["error"] == "InvalidInputError"
    assert client.put(f"/api/projects/{pid}/artifacts/Not_Safe", json={"text": "x"}).status_code == 404
