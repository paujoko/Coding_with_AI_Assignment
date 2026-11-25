"""Deleting a project: Wings forgets it, the developer's folder stays as it is."""

import pytest

from wings.adapters.fs_store import FileSystemStore
from wings.domain.errors import ConflictError, NotFoundError
from wings.domain.phases import PhaseId as P


def test_delete_removes_the_project_and_everything_wings_kept(make_orchestrator, demo_script, walk, tmp_path):
    orch = make_orchestrator(demo_script)
    pid = walk(orch, P.DESIGN)
    other = orch.create_project("Other").id
    assert orch.store.list_artifacts(pid)

    orch.delete_project(pid)

    assert [p.id for p in orch.list_projects()] == [other]
    with pytest.raises(NotFoundError):
        orch.project(pid)
    assert not (tmp_path / "ws" / pid).exists()
    assert orch.project(other).id == other  # the other project is untouched


def test_a_new_project_with_the_same_name_starts_empty(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = walk(orch, P.DESIGN)
    orch.delete_project(pid)

    again = orch.create_project("Todo")

    assert again.id == pid  # the id is free again
    assert orch.store.list_artifacts(again.id) == []
    assert orch.store.list_events(again.id)[0].kind == "project.created"


def test_delete_keeps_the_developers_folder(make_orchestrator, demo_script, walk, tmp_path):
    from wings.adapters.project_folder import LocalProjectFolder

    orch = make_orchestrator(demo_script)
    orch.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home", projects_dir=tmp_path / "WingsProjects")
    pid = walk(orch, P.REFINEMENT)
    folder = tmp_path / "WingsProjects" / "todo"
    (folder / "notes.txt").write_text("mine", encoding="utf-8")
    before = sorted(p.relative_to(folder) for p in folder.rglob("*"))
    assert before  # Wings wrote files into it

    orch.delete_project(pid)

    assert sorted(p.relative_to(folder) for p in folder.rglob("*")) == before
    assert (folder / "notes.txt").read_text(encoding="utf-8") == "mine"


def test_delete_of_an_unknown_project_is_not_found(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    with pytest.raises(NotFoundError):
        orch.delete_project("nope")
    with pytest.raises(NotFoundError):
        orch.delete_project("../escape")


def test_delete_is_refused_while_an_agent_works_on_the_project(make_orchestrator, demo_script):
    orch = make_orchestrator(demo_script)
    pid = orch.create_project("Todo").id
    with orch._claim(pid, P.REQUIREMENTS, "start", "Write requirements"):
        with pytest.raises(ConflictError, match="agent is working"):
            orch.delete_project(pid)
    orch.delete_project(pid)
    assert orch.list_projects() == []


def test_store_leaves_no_project_behind_when_the_folder_cannot_be_removed(tmp_path, monkeypatch):
    """Windows can hold a file open; the project must still be gone from the list and its id free."""
    import shutil

    from wings.domain.project import Project

    store = FileSystemStore(tmp_path / "ws")
    store.save_project(Project.new("Todo", {}, project_id="todo"))

    def stuck(path, *args, **kwargs):
        raise PermissionError("held open")

    monkeypatch.setattr(shutil, "rmtree", stuck)
    store.delete_project("todo")

    assert store.list_projects() == []
    assert not store.project_exists("todo")
    assert not (tmp_path / "ws" / "todo").exists()
