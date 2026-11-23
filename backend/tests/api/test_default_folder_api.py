"""HTTP: the default folder of a project (GET /system/default-folder, POST /projects without a folder)."""

import pytest
from fastapi.testclient import TestClient

from wings.adapters.project_folder import LocalProjectFolder
from wings.api.app import create_app
from wings.bootstrap import build_container
from wings.config import Settings


@pytest.fixture
def client(make_orchestrator, demo_script, tmp_path):
    orch = make_orchestrator(demo_script)
    orch.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home", projects_dir=tmp_path / "WingsProjects")
    return TestClient(create_app(orch, {"llm_provider": "mock"}))


def test_default_folder_has_exactly_one_field(client, tmp_path):
    base = tmp_path / "WingsProjects"
    assert client.get("/api/system/default-folder", params={"name": "Todo App"}).json() == {"path": str(base / "todo-app")}
    assert client.get("/api/system/default-folder", params={"name": ""}).json() == {"path": str(base / "project")}
    assert client.get("/api/system/default-folder").json() == {"path": str(base / "project")}
    assert not base.exists()  # asking creates nothing


def test_create_without_a_folder_uses_the_default_and_the_next_one_gets_a_number(client, tmp_path):
    base = tmp_path / "WingsProjects"
    first = client.post("/api/projects", json={"name": "Todo App"})
    assert first.status_code == 201 and first.json()["folder"]["path"] == str(base / "todo-app")
    assert (base / "todo-app").is_dir()
    assert client.get("/api/system/default-folder", params={"name": "Todo App"}).json() == {"path": str(base / "todo-app-2")}
    assert client.post("/api/projects", json={"name": "Todo App"}).json()["folder"]["path"] == str(base / "todo-app-2")


def test_create_with_a_folder_behaves_as_before(client, tmp_path):
    made = client.post("/api/projects", json={"name": "Todo", "folder": str(tmp_path / "mine")}).json()
    assert made["folder"]["path"] == str(tmp_path / "mine")
    assert not (tmp_path / "WingsProjects").exists()


def test_without_a_projects_dir_the_path_is_null_and_no_folder_is_linked(make_orchestrator, demo_script):
    api = TestClient(create_app(make_orchestrator(demo_script), {"llm_provider": "mock"}))
    assert api.get("/api/system/default-folder", params={"name": "Todo"}).json() == {"path": None}
    assert api.post("/api/projects", json={"name": "Todo"}).json()["folder"] is None


def test_bootstrap_hands_the_projects_dir_to_the_folder_adapter(tmp_path):
    container = build_container(Settings(workspace_dir=tmp_path / "ws", projects_dir=tmp_path / "projects"))
    assert container.orchestrator.default_folder("Todo") == str(tmp_path / "projects" / "todo")
    assert build_container(Settings(workspace_dir=tmp_path / "ws2")).orchestrator.default_folder("Todo") is None
