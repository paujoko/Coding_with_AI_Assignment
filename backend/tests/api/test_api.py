import pytest
from fastapi.testclient import TestClient

from wings.api.app import API_VERSION, create_app


@pytest.fixture
def client(make_orchestrator, demo_script):
    return TestClient(create_app(make_orchestrator(demo_script), {"llm_provider": "mock"}))


def act(client, pid, phase, action, **input):
    return client.post(f"/api/projects/{pid}/phases/{phase}/actions/{action}", json={"input": input})


def test_health_and_phase_catalog(client):
    health = client.get("/api/health").json()
    assert health["llm_provider"] == "mock"
    # The UI compares this with the version it was built for (frontend/src/api/client.ts).
    assert health["api_version"] == API_VERSION == 5
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

    trace = client.get(f"/api/projects/{pid}/trace").json()
    assert trace["uncovered"] == []
    assert trace["requirements"][0] == {"id": "REQ-001", "title": "Add a task"}
    linked = {a["id"]: a for a in trace["artifacts"]}
    assert set(trace["covered"]["REQ-001"]) <= set(linked)
    assert linked[trace["covered"]["REQ-001"][0]]["phase"] == "design"
    assert all({"title", "kind", "covers"} <= set(a) for a in trace["artifacts"])
    assert len(client.get(f"/api/projects/{pid}/artifacts", params={"phase": "design"}).json()) == 3
    msgs = client.get(f"/api/projects/{pid}/messages", params={"phase": "requirements"}).json()
    assert [m["role"] for m in msgs] == ["developer", "agent", "developer", "agent"]
    seqs = [e["seq"] for e in client.get(f"/api/projects/{pid}/events", params={"after": 3}).json()]
    assert seqs and seqs[0] == 4


def test_errors_map_to_http_codes(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    assert act(client, pid, "design", "generate").status_code == 409  # locked
    assert act(client, pid, "codegen", "generate").status_code == 409  # locked until refinement is approved
    assert act(client, pid, "requirements", "nope").status_code == 404
    assert act(client, pid, "nonsense", "start").status_code == 404
    assert client.get("/api/projects/missing").status_code == 404
    assert act(client, pid, "requirements", "start").status_code == 422  # description missing
    assert client.post(f"/api/projects/{pid}/phases/requirements/approve").status_code == 409


def test_stale_phase_names_its_cause(client):
    pid = client.post("/api/projects", json={"name": "Cause"}).json()["id"]
    act(client, pid, "requirements", "start", description="A todo app")
    act(client, pid, "requirements", "answer", answers="CLI")
    client.post(f"/api/projects/{pid}/phases/requirements/approve")
    act(client, pid, "design", "generate")
    client.post(f"/api/projects/{pid}/phases/requirements/reopen")
    act(client, pid, "requirements", "revise", feedback="Add tags")
    design = client.get(f"/api/projects/{pid}").json()["phases"][1]
    assert design["status"] == "stale" and design["stale_cause"] == "requirements"


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


def test_upload_a_document_and_attach_it_to_an_action(client):
    import base64

    pid = client.post("/api/projects", json={"name": "Upload"}).json()["id"]
    body = {"name": "brief.md", "media_type": "text/markdown", "content_base64": base64.b64encode(b"Rooms per hour").decode()}
    r = client.post(f"/api/projects/{pid}/attachments", json=body)
    assert r.status_code == 201
    att = r.json()
    assert att["id"] == "att-001" and att["chars"] == 14 and "text" not in att

    assert [a["name"] for a in client.get(f"/api/projects/{pid}/attachments").json()] == ["brief.md"]
    assert client.get(f"/api/projects/{pid}/attachments/att-001").json()["text"] == "Rooms per hour"

    r = act(client, pid, "requirements", "start", description="A booking tool")
    r = client.post(f"/api/projects/{pid}/phases/requirements/actions/answer", json={"input": {"answers": "CLI"}, "attachments": ["att-001"]})
    assert r.status_code == 200
    msgs = client.get(f"/api/projects/{pid}/messages", params={"phase": "requirements"}).json()
    assert msgs[2]["data"]["attachments"] == [{"id": "att-001", "name": "brief.md"}]


def test_bad_uploads_are_422(client):
    pid = client.post("/api/projects", json={"name": "Bad upload"}).json()["id"]
    bad = client.post(f"/api/projects/{pid}/attachments", json={"name": "x.txt", "media_type": "text/plain", "content_base64": "%%%"})
    assert bad.status_code == 422
    image = client.post(f"/api/projects/{pid}/attachments", json={"name": "x.png", "media_type": "image/png", "content_base64": "iVBORw0K"})
    assert image.status_code == 422 and "supported" in image.json()["detail"]
    unknown = client.post(f"/api/projects/{pid}/phases/requirements/actions/start", json={"input": {"description": "x"}, "attachments": ["att-404"]})
    assert unknown.status_code == 422


def test_settings_never_return_the_key(tmp_path):
    from wings.bootstrap import LLMSettings, build_container
    from wings.config import Settings

    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    api = TestClient(create_app(container.orchestrator, container.info, settings=LLMSettings(container, env_file=tmp_path / ".env")))
    assert api.get("/api/settings").json()["provider"] == "mock"
    r = api.put("/api/settings/llm", json={"provider": "openai", "api_key": "sk-secret-9999"})
    assert r.status_code == 200 and "sk-secret-9999" not in r.text and r.json()["key_hint"] == "sk-…9999"
    assert api.get("/api/health").json()["llm_provider"] == "openai"
    assert api.put("/api/settings/llm", json={"provider": "gemini"}).status_code == 422
    api.put("/api/settings/llm", json={"provider": "mock"})
    assert api.post("/api/settings/llm/test").json()["ok"] is True
