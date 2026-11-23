import pytest

from wings.adapters.project_folder import LocalProjectFolder
from wings.domain.errors import InvalidInputError


@pytest.fixture
def folders(tmp_path):
    wings_repo = tmp_path / "wings"
    (wings_repo / "workspaces").mkdir(parents=True)
    return LocalProjectFolder(forbidden=[wings_repo], home=tmp_path / "home"), tmp_path


def test_a_new_folder_inside_an_existing_one_is_fine_and_created_on_prepare(folders):
    port, tmp = folders
    target = tmp / "projects" / "todo"
    (tmp / "projects").mkdir()
    assert port.problem(str(target)) is None
    assert not port.exists(str(target))
    port.prepare(str(target))
    assert target.is_dir() and list(target.iterdir()) == []


@pytest.mark.parametrize(
    "path, words",
    [
        ("", "full path"),
        ("relative/todo", "not a full path"),
    ],
)
def test_unusable_paths_are_explained(folders, path, words):
    port, _ = folders
    assert words in port.problem(path)


def test_a_drive_or_filesystem_root_is_too_broad(folders):
    port, tmp = folders
    assert "too broad" in port.problem(tmp.anchor)  # "/" on Linux and macOS, "C:\\" on Windows


def test_wings_own_folders_and_the_home_folder_are_refused(folders):
    port, tmp = folders
    assert "overlaps" in port.problem(str(tmp / "wings" / "workspaces" / "x"))
    assert "overlaps" in port.problem(str(tmp))  # would contain the Wings repository
    (tmp / "home").mkdir()
    assert "too broad" in port.problem(str(tmp / "home"))


def test_a_missing_parent_or_a_file_is_refused(folders):
    port, tmp = folders
    assert "does not exist" in port.problem(str(tmp / "nope" / "todo"))
    (tmp / "file.txt").write_text("x")
    assert "is a file" in port.problem(str(tmp / "file.txt"))
    with pytest.raises(InvalidInputError):
        port.prepare(str(tmp / "nope" / "todo"))


def test_write_read_and_delete(folders):
    port, tmp = folders
    root = str(tmp / "todo")
    port.prepare(root)
    port.write_file(root, "todo/models.py", "class Task:\n    pass\n")
    port.write_file(root, "docs/wings/requirements.md", "# R\n")
    assert port.read_files(root) == {"docs/wings/requirements.md": "# R\n", "todo/models.py": "class Task:\n    pass\n"}
    assert (tmp / "todo" / "todo" / "models.py").read_bytes() == b"class Task:\n    pass\n"  # \n, also on Windows
    port.delete_file(root, "todo/models.py")
    assert not (tmp / "todo" / "todo").exists()  # the empty folder went with it
    assert (tmp / "todo").is_dir()


def test_tool_folders_binary_and_temporary_files_are_not_read(folders):
    port, tmp = folders
    root = tmp / "todo"
    for rel, data in {
        ".git/config": b"x",
        ".venv/lib/site.py": b"x",
        "todo/__pycache__/m.pyc": b"x",
        "node_modules/a/index.js": b"x",
        "logo.png": b"\x89PNG\r\n\x1a\n\xff\xfe",
        ".wings-models.py.tmp": b"x",
        "todo/models.py": b"x = 1\r\n",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    assert port.read_files(str(root)) == {"todo/models.py": "x = 1\r\n"}


@pytest.mark.parametrize("rel", ["../outside.py", "/etc/passwd", "a\\b.py", "C:/x.py", ""])
def test_nothing_is_written_outside_the_folder(folders, rel):
    port, tmp = folders
    port.prepare(str(tmp / "todo"))
    with pytest.raises(ValueError):
        port.write_file(str(tmp / "todo"), rel, "x")
