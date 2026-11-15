"""Two-way sync with the developer's output folder (ADR 0015), through the orchestrator on the demo script."""

import json

import pytest

from wings.adapters.documents import DocumentTextExtractor
from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.adapters.project_folder import LocalProjectFolder
from wings.adapters.sandbox import LocalSandbox
from wings.application.orchestrator import Orchestrator
from wings.bootstrap import build_registry
from wings.config import DEFAULT_MOCK_SCRIPT
from wings.domain.errors import InvalidInputError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S
from tests.conftest import as_text, walk_to


@pytest.fixture
def orch(tmp_path) -> Orchestrator:
    script = json.loads(DEFAULT_MOCK_SCRIPT.read_text(encoding="utf-8"))
    llm = ScriptedLLM({agent: [as_text(r) for r in replies] for agent, replies in script.items()})
    store_dir = tmp_path / "wings" / "workspaces"
    return Orchestrator(
        build_registry(),
        FileSystemStore(store_dir),
        llm,
        PlantUMLRenderer(),
        extractor=DocumentTextExtractor(),
        sandbox=LocalSandbox(),
        folder=LocalProjectFolder(forbidden=[tmp_path / "wings"], home=tmp_path / "home"),
    )


def test_a_project_created_with_a_folder_writes_every_change_there(orch, tmp_path):
    target = tmp_path / "todo-app"
    pid = orch.create_project("Todo", folder=str(target)).id
    assert orch.project(pid).folder.path == str(target)
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "A todo app"})
    orch.run_action(pid, P.REQUIREMENTS, "answer", {"answers": "CLI"})
    assert (target / "docs" / "wings" / "requirements.md").read_text(encoding="utf-8").startswith("#")
    assert orch.folder_status(pid).changes == []
    kinds = [e.kind for e in orch.store.list_events(pid)]
    assert "folder.linked" in kinds and "folder.synced" in kinds


def test_the_folder_mirrors_code_tests_and_deployment_at_the_top(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    assert (target / "todo" / "models.py").is_file()
    assert (target / "tests" / "test_tasks.py").is_file()
    assert (target / "Dockerfile").is_file() and (target / "run.ps1").is_file()
    assert (target / "docs" / "wings" / "design").is_dir()
    assert orch.folder_status(pid).changes == []


def test_a_folder_with_files_or_inside_wings_is_refused(orch, tmp_path):
    pid = orch.create_project("Todo").id
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "notes.txt").write_text("mine")
    with pytest.raises(InvalidInputError, match="already has files"):
        orch.set_folder(pid, str(busy))
    with pytest.raises(InvalidInputError, match="overlaps"):
        orch.set_folder(pid, str(tmp_path / "wings" / "workspaces" / "x"))
    with pytest.raises(InvalidInputError, match="already has files"):
        orch.create_project("Other", folder=str(busy))
    assert [p.name for p in orch.list_projects()] == ["Todo"]  # nothing created when the folder is refused


def test_a_hand_edit_is_imported_checked_against_the_design_and_propagates(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    models = target / "todo" / "models.py"
    models.write_text(models.read_text(encoding="utf-8") + "\n    def archive(self) -> None:\n        self.done = True\n", encoding="utf-8")

    [change] = orch.folder_status(pid).changes
    assert (change.path, change.change, change.phase, change.importable) == ("todo/models.py", "modified", P.CODEGEN, True)

    result = orch.import_folder_changes(pid)
    assert [c.path for c in result.imported] == ["todo/models.py"]
    assert any("archive() is in the code but not in the class diagram" in line for line in result.drift)
    saved = orch.store.get_artifact(pid, "source-todo-models-py")
    assert saved.author == "developer" and "def archive" in saved.text
    project = orch.project(pid)
    assert project.status(P.CODEGEN) is S.DRAFT
    assert project.status(P.TESTING) is S.STALE and project.status(P.DEPLOYMENT) is S.STALE
    assert orch.folder_status(pid).changes == []  # the folder and Wings agree again

    [message] = [m for m in orch.store.list_messages(pid, P.CODEGEN) if m.author == "Folder sync (code)"]
    assert message.data["speaker"] == "Folder sync, checked by code"  # no agent wrote it, and the chat says so
    labels = [a["label"] for a in message.data["next_actions"]]
    assert labels == ["Update the design from the code", "Update the code from the design"]


def test_crlf_from_a_windows_editor_is_not_a_change(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    models = target / "todo" / "models.py"
    models.write_bytes(models.read_bytes().replace(b"\n", b"\r\n"))
    assert orch.folder_status(pid).changes == []


def test_wings_never_overwrites_a_hand_edit_when_it_regenerates(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    readme = target / "DEPLOY.md"
    readme.write_text("my own notes\n", encoding="utf-8")
    orch.reopen(pid, P.DEPLOYMENT)
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})  # a newer revision of DEPLOY.md
    assert readme.read_text(encoding="utf-8") == "my own notes\n"
    [change] = orch.folder_status(pid).changes
    assert change.path == "DEPLOY.md" and change.newer_in_wings
    assert any(e.kind == "folder.synced" and "DEPLOY.md" in e.data.get("kept", []) for e in orch.store.list_events(pid))


def test_restore_puts_wings_version_back(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    original = (target / "todo" / "models.py").read_text(encoding="utf-8")
    (target / "todo" / "models.py").write_text("broken", encoding="utf-8")
    (target / "run.sh").unlink()
    status = orch.restore_folder_files(pid, ["todo/models.py", "run.sh"])
    assert status.changes == []
    assert (target / "todo" / "models.py").read_text(encoding="utf-8") == original and (target / "run.sh").is_file()
    with pytest.raises(InvalidInputError, match="Not a changed"):
        orch.restore_folder_files(pid, ["todo/service.py"])


def test_new_code_and_test_files_are_adopted_by_their_wings(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    (target / "todo" / "export.py").write_text("def to_csv(tasks):\n    return ''\n", encoding="utf-8")
    (target / "tests" / "test_export.py").write_text("def test_nothing():\n    assert True\n", encoding="utf-8")
    (target / "tasks.json").write_text("[]", encoding="utf-8")  # data the program writes: not offered
    changes = {c.path: c for c in orch.folder_status(pid).changes}
    assert set(changes) == {"todo/export.py", "tests/test_export.py"}
    assert changes["todo/export.py"].phase is P.CODEGEN and changes["tests/test_export.py"].phase is P.TESTING

    orch.import_folder_changes(pid, ["todo/export.py", "tests/test_export.py"])
    assert orch.store.get_artifact(pid, "source-todo-export-py").author == "developer"
    assert orch.store.get_artifact(pid, "test-test-export-py").path == "app/tests/test_export.py"
    project = orch.project(pid)
    assert project.status(P.CODEGEN) is S.DRAFT and project.status(P.TESTING) is S.DRAFT  # both edited: draft, not stale
    assert project.status(P.DEPLOYMENT) is S.STALE


def test_invalid_python_is_shown_but_not_importable(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    (target / "todo" / "models.py").write_text("class Task(\n", encoding="utf-8")
    [change] = orch.folder_status(pid).changes
    assert not change.importable and "Cannot be imported" in change.note
    with pytest.raises(InvalidInputError, match="Nothing to import"):
        orch.import_folder_changes(pid)
    assert orch.store.get_artifact(pid, "source-todo-models-py").author != "developer"


def test_deleting_a_code_file_by_hand_retires_it_on_import(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    (target / "todo" / "cli.py").unlink()
    [change] = orch.folder_status(pid).changes
    assert change.change == "deleted" and change.importable
    orch.import_folder_changes(pid)
    assert orch.store.get_artifact(pid, "source-todo-cli-py").retired


def test_a_hand_edit_of_a_diagram_is_imported_into_its_phase(orch, tmp_path):
    pid = walk_to(orch, P.MAINTENANCE)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    [puml] = [p for p in (target / "docs" / "wings" / "refinement").glob("*.puml") if "class" in p.read_text(encoding="utf-8")][:1]
    puml.write_text(puml.read_text(encoding="utf-8").replace("@enduml", "class Archive\n@enduml"), encoding="utf-8")
    result = orch.import_folder_changes(pid)
    assert result.imported[0].phase is P.REFINEMENT
    assert "Archive is in the class diagram but not in the code." in result.drift
    assert orch.project(pid).status(P.CODEGEN) is S.STALE


def test_a_missing_folder_is_reported_and_does_not_break_actions(orch, tmp_path):
    pid = walk_to(orch, P.DEPLOYMENT)
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    import shutil

    shutil.rmtree(target)
    status = orch.folder_status(pid)
    assert not status.exists and "not there" in status.problem
    orch.run_action(pid, P.DEPLOYMENT, "generate", {})  # still works
    assert any(e.kind == "folder.error" for e in orch.store.list_events(pid))


def test_unlinking_keeps_the_files(orch, tmp_path):
    target = tmp_path / "todo-app"
    pid = orch.create_project("Todo", folder=str(target)).id
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "A todo app"})
    orch.run_action(pid, P.REQUIREMENTS, "answer", {"answers": "CLI"})
    assert orch.set_folder(pid, None).path is None
    assert orch.project(pid).folder is None
    assert (target / "docs" / "wings" / "requirements.md").exists()


def test_design_check_says_whether_out_of_date_code_still_fits(orch, tmp_path):
    """Session s04, Ben's run: after 'Update the design from the code' the code was out of date although it
    already matched the new class diagram, and the hint only said 'approve it again if it still fits'."""
    pid = walk_to(orch, P.MAINTENANCE)
    assert orch.design_check(pid).in_sync
    target = tmp_path / "todo-app"
    orch.set_folder(pid, str(target))
    models = target / "todo" / "models.py"
    models.write_text(models.read_text(encoding="utf-8") + "\n    def archive(self) -> None:\n        self.done = True\n", encoding="utf-8")
    orch.import_folder_changes(pid)
    check = orch.design_check(pid)
    assert not check.in_sync and check.lines == ["Task.archive() is in the code but not in the class diagram."]
    [message] = [m for m in orch.store.list_messages(pid, P.CODEGEN) if m.author == "Folder sync (code)"]
    assert message.data["drift"] == check.lines

    # The developer updates the class diagram by hand (what the refiner would do), the code is now out of date ...
    diagram = next(a for a in orch.store.list_artifacts(pid, P.REFINEMENT) if a.content.get("kind") == "class")
    orch.update_artifact(pid, diagram.id, text=diagram.text.replace("class Task {", "class Task {\n  +archive()", 1))
    orch.approve(pid, P.REFINEMENT)
    assert orch.project(pid).status(P.CODEGEN) is S.STALE
    # ... but code says it still fits.
    assert orch.design_check(pid).in_sync


def test_no_design_check_before_there_is_code(orch):
    pid = walk_to(orch, P.CODEGEN)
    assert orch.design_check(pid) is None
