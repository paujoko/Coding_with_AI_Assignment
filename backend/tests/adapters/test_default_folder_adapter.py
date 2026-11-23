"""The folder adapter: the default place for a project, what "empty" means, two spellings of one folder."""

import os

import pytest

from wings.adapters.project_folder import MAX_BYTES, LocalProjectFolder
from wings.domain.errors import InvalidInputError


@pytest.fixture
def port(tmp_path):
    return LocalProjectFolder(forbidden=[tmp_path / "wings"], home=tmp_path / "home", projects_dir=tmp_path / "WingsProjects")


def test_the_default_path_is_the_projects_dir_plus_the_name(port, tmp_path):
    assert port.default_path("todo-app") == str(tmp_path / "WingsProjects" / "todo-app")
    assert not (tmp_path / "WingsProjects").exists()  # asking creates nothing


def test_no_projects_dir_means_no_default(tmp_path):
    assert LocalProjectFolder(home=tmp_path / "home").default_path("todo-app") is None


@pytest.mark.parametrize("name", ["", "..", ".", "a/b", "a\\b", "c:x"])
def test_a_name_that_is_not_one_folder_name_gets_no_default(port, name):
    assert port.default_path(name) is None


def test_the_projects_dir_is_created_when_a_project_is_linked_there(port, tmp_path):
    target = port.default_path("todo-app")
    assert port.problem(target) is None  # the missing parent is fine here, and only here
    port.prepare(target)
    assert (tmp_path / "WingsProjects" / "todo-app").is_dir()


def test_any_other_missing_parent_is_still_refused(port, tmp_path):
    assert "does not exist" in port.problem(str(tmp_path / "nowhere" / "todo-app"))
    with pytest.raises(InvalidInputError):
        port.prepare(str(tmp_path / "nowhere" / "todo-app"))
    assert not (tmp_path / "nowhere").exists()


def test_a_missing_folder_and_a_fresh_git_init_are_empty(port, tmp_path):
    assert port.is_empty(str(tmp_path / "new"))
    repo = tmp_path / "repo"
    (repo / ".git" / "objects").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (repo / "desktop.ini").write_text("", encoding="utf-8")
    assert port.is_empty(str(repo))


def test_binary_files_big_files_and_dot_folders_are_content(port, tmp_path):
    """These are invisible to read_files, which used to make such a folder look empty."""
    binary = tmp_path / "photos"
    binary.mkdir()
    (binary / "cat.png").write_bytes(b"\x89PNG\xff\xfe\x00")
    big = tmp_path / "big"
    big.mkdir()
    (big / "dump.txt").write_bytes(b"a" * (MAX_BYTES + 1))
    dotted = tmp_path / "dotted"
    (dotted / ".obsidian").mkdir(parents=True)
    (dotted / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    for folder in (binary, big, dotted):
        assert port.read_files(str(folder)) == {}
        assert not port.is_empty(str(folder))
    file = tmp_path / "a-file"
    file.write_text("x", encoding="utf-8")
    assert not port.is_empty(str(file))


def test_two_spellings_of_one_folder_are_the_same(port, tmp_path):
    folder = tmp_path / "Todo"
    folder.mkdir()
    assert port.same(str(folder), str(folder) + os.sep)
    assert port.same(str(folder), str(tmp_path / "x" / ".." / "Todo"))
    assert port.same(str(folder), "  " + str(folder) + " ")
    assert not port.same(str(folder), str(tmp_path / "Todo2"))
    if os.name == "nt":
        assert port.same(str(folder), str(folder).swapcase())
        assert port.same(str(folder), str(folder).replace("\\", "/"))
