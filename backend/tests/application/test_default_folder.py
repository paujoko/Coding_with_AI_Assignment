"""A project always gets a folder: the default place, numbering, and folders compared as folders, not as text."""

import os
import threading

import pytest

from wings.adapters.project_folder import LocalProjectFolder
from wings.domain.errors import InvalidInputError


@pytest.fixture
def orch(make_orchestrator, demo_script, tmp_path):
    o = make_orchestrator(demo_script)
    o.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home", projects_dir=tmp_path / "WingsProjects")
    return o


def test_a_project_without_a_named_folder_gets_the_default_one(orch, tmp_path):
    project = orch.create_project("Todo App")
    assert project.folder is not None and project.folder.path == str(tmp_path / "WingsProjects" / "todo-app")
    assert (tmp_path / "WingsProjects" / "todo-app").is_dir()
    assert [e.kind for e in orch.store.list_events(project.id)][:2] == ["project.created", "folder.linked"]
    assert orch.folder_status(project.id).problem is None


def test_a_named_folder_wins_over_the_default(orch, tmp_path):
    project = orch.create_project("Todo App", folder=str(tmp_path / "mine"))
    assert project.folder.path == str(tmp_path / "mine")
    assert not (tmp_path / "WingsProjects").exists()


def test_without_a_projects_dir_nothing_changes(make_orchestrator, demo_script, tmp_path):
    bare = make_orchestrator(demo_script)
    assert bare.default_folder("Todo") is None and bare.create_project("Todo").folder is None
    bare.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home")
    assert bare.default_folder("Todo") is None and bare.create_project("Todo").folder is None


def test_a_taken_default_folder_gets_a_number(orch, tmp_path):
    base = tmp_path / "WingsProjects"
    (base / "todo").mkdir(parents=True)
    (base / "todo" / "notes.txt").write_text("mine", encoding="utf-8")
    (base / "todo-2").mkdir()
    (base / "todo-2" / "photo.png").write_bytes(b"\x89PNG\xff\x00")  # binary only: still not free
    assert orch.default_folder("Todo") == str(base / "todo-3")
    assert orch.create_project("Todo").folder.path == str(base / "todo-3")
    assert (base / "todo" / "notes.txt").read_text(encoding="utf-8") == "mine"


def test_an_existing_empty_default_folder_and_a_fresh_git_init_are_used(orch, tmp_path):
    base = tmp_path / "WingsProjects"
    (base / "todo" / ".git").mkdir(parents=True)
    assert orch.default_folder("Todo") == str(base / "todo")


def test_two_projects_with_one_name_never_share_a_folder(orch, tmp_path):
    """The first project's folder is still empty when the second is created."""
    first, second = orch.create_project("Todo"), orch.create_project("Todo")
    assert first.folder.path == str(tmp_path / "WingsProjects" / "todo")
    assert second.folder.path == str(tmp_path / "WingsProjects" / "todo-2")


def test_creating_at_the_same_time_never_shares_a_folder(orch):
    made, errors = [], []

    def create() -> None:
        try:
            made.append(orch.create_project("Todo"))
        except BaseException as err:  # noqa: BLE001 - the test reports whatever went wrong
            errors.append(err)

    threads = [threading.Thread(target=create) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len({p.folder.path for p in made}) == 6 and len({p.id for p in made}) == 6


def test_an_empty_name_asks_for_the_folder_of_the_slug_project(orch, tmp_path):
    assert orch.default_folder("") == str(tmp_path / "WingsProjects" / "project")
    assert orch.default_folder("  !!  ") == str(tmp_path / "WingsProjects" / "project")
    assert not (tmp_path / "WingsProjects").exists()


def test_a_default_place_that_cannot_be_used_stops_the_create(make_orchestrator, demo_script, tmp_path):
    o = make_orchestrator(demo_script)
    o.folder = LocalProjectFolder(forbidden=[tmp_path / "ws"], home=tmp_path / "home", projects_dir=tmp_path / "ws" / "inside")
    with pytest.raises(InvalidInputError, match="overlaps"):
        o.create_project("Todo")
    assert o.list_projects() == []


def test_setting_the_same_folder_in_another_spelling_keeps_the_link(orch, tmp_path):
    target = tmp_path / "Mine"
    project = orch.create_project("Todo", folder=str(target))
    (target / "notes.txt").write_text("a hand-made file", encoding="utf-8")  # the folder is no longer empty
    other = str(target) + os.sep
    if os.name == "nt":
        other = other.swapcase()
    orch.set_folder(project.id, other)  # must not be refused as "already has files", must not be linked again
    after = orch.project(project.id)
    assert after.folder.path == str(target)
    assert [e.kind for e in orch.store.list_events(project.id)].count("folder.linked") == 1


def test_a_folder_with_only_binary_files_is_not_taken_for_empty(orch, tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    (photos / "cat.png").write_bytes(b"\x89PNG\xff\x00")
    with pytest.raises(InvalidInputError, match="already has files"):
        orch.create_project("Todo", folder=str(photos))
    hidden = tmp_path / "vault"
    (hidden / ".obsidian").mkdir(parents=True)
    project = orch.create_project("Other", folder=str(tmp_path / "ok"))
    with pytest.raises(InvalidInputError, match="already has files"):
        orch.set_folder(project.id, str(hidden))


def test_a_fresh_git_repository_can_be_chosen(orch, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert orch.create_project("Todo", folder=str(repo)).folder.path == str(repo)
