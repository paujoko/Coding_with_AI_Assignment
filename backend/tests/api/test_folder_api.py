"""HTTP routes of the output folder (ADR 0015)."""

import pytest
from fastapi.testclient import TestClient

from wings.adapters.project_folder import LocalProjectFolder
from wings.api.app import create_app


@pytest.fixture
def client(make_orchestrator, demo_script, tmp_path):
    orch = make_orchestrator(demo_script)
    orch.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home")
    return TestClient(create_app(orch, {"llm_provider": "mock"}))


def act(client, pid, phase, action, **input):
    return client.post(f"/api/projects/{pid}/phases/{phase}/actions/{action}", json={"input": input})


def test_create_with_a_folder_then_edit_import_and_restore(client, tmp_path):
    target = tmp_path / "todo-app"
    project = client.post("/api/projects", json={"name": "Todo", "folder": str(target)}).json()
    pid = project["id"]
    assert project["folder"]["path"] == str(target)
    act(client, pid, "requirements", "start", description="A todo app")
    act(client, pid, "requirements", "answer", answers="CLI")
    client.post(f"/api/projects/{pid}/phases/requirements/approve")
    act(client, pid, "design", "generate")
    assert client.get(f"/api/projects/{pid}/folder").json() == {"path": str(target), "exists": True, "changes": [], "problem": None}

    [puml] = sorted((target / "docs" / "wings" / "design").glob("*.puml"))[:1]
    puml.write_text(puml.read_text(encoding="utf-8").replace("@enduml", "' a note\n@enduml"), encoding="utf-8")
    [change] = client.get(f"/api/projects/{pid}/folder").json()["changes"]
    assert change["change"] == "modified" and change["importable"] and change["phase"] == "design"

    restored = client.post(f"/api/projects/{pid}/folder/restore", json={"paths": [change["path"]]}).json()
    assert restored["changes"] == []

    puml.write_text(puml.read_text(encoding="utf-8").replace("@enduml", "' a note\n@enduml"), encoding="utf-8")
    result = client.post(f"/api/projects/{pid}/folder/import", json={}).json()
    assert [c["path"] for c in result["imported"]] == [change["path"]]
    assert result["project"]["phases"][1]["status"] == "draft"
    assert "Imported from your folder" in result["reply"]


def test_folder_errors_are_422_with_a_reason(client, tmp_path):
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x.txt").write_text("x")
    r = client.post("/api/projects", json={"name": "Todo", "folder": str(busy)})
    assert r.status_code == 422 and "already has files" in r.json()["detail"]
    pid = client.post("/api/projects", json={"name": "Todo"}).json()["id"]
    r = client.put(f"/api/projects/{pid}/folder", json={"path": "relative/path"})
    assert r.status_code == 422 and "not a full path" in r.json()["detail"]
    r = client.post(f"/api/projects/{pid}/folder/import", json={})
    assert r.status_code == 422


def test_link_later_and_unlink(client, tmp_path):
    pid = client.post("/api/projects", json={"name": "Todo"}).json()["id"]
    assert client.get(f"/api/projects/{pid}").json()["folder"] is None
    linked = client.put(f"/api/projects/{pid}/folder", json={"path": str(tmp_path / "later")}).json()
    assert linked["path"] == str(tmp_path / "later") and linked["project"]["folder"]["path"] == str(tmp_path / "later")
    unlinked = client.put(f"/api/projects/{pid}/folder", json={"path": None}).json()
    assert unlinked["path"] is None and unlinked["project"]["folder"] is None


class FakePicker:
    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def pick(self, start=None, title=""):
        self.asked.append(start)
        return self.answer


def test_pick_folder_opens_the_dialog_and_suggests_a_subfolder_for_a_busy_one(make_orchestrator, demo_script, tmp_path):
    orch = make_orchestrator(demo_script)
    orch.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home")
    projects = tmp_path / "Projects"
    (projects / "old").mkdir(parents=True)
    (projects / "old" / "x.py").write_text("x = 1")
    picker = FakePicker(str(projects))
    api = TestClient(create_app(orch, {}, picker=picker))
    assert api.get("/api/health").json()["folder_picker"] is True
    out = api.post("/api/system/pick-folder", json={"start": str(tmp_path), "name": "To-do app"}).json()
    assert out == {"path": str(projects), "empty": False, "suggested": str(projects / "to-do-app")}
    assert picker.asked == [str(tmp_path)]
    picker.answer = str(tmp_path / "new")
    assert api.post("/api/system/pick-folder", json={}).json() == {"path": str(tmp_path / "new"), "empty": True, "suggested": None}
    picker.answer = None
    assert api.post("/api/system/pick-folder", json={}).json()["path"] is None


def test_no_picker_no_route(client):
    assert client.post("/api/system/pick-folder", json={}).status_code in (404, 405)
    assert client.get("/api/health").json()["folder_picker"] is False
