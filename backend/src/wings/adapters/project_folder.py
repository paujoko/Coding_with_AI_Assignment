"""Filesystem implementation of the ProjectFolder port: the developer's own folder for a project (ADR 0015).

Rules this adapter enforces, whatever the core asks:
- the folder is an absolute path whose parent exists; drive roots, the home folder itself and
  Wings' own folders (the repository, the workspaces) are refused;
- a project without a named folder gets `<projects dir>/<name>`; the projects dir is the one parent
  this adapter creates itself, and only when a project is really linked there;
- "empty" means nothing in the folder but a fresh `.git` (and the operating system's own files), so a
  folder holding only pictures, big files or dot-folders is never taken for a free one;
- every file read or written resolves inside the folder (no `..`, no absolute paths, no links out);
- tool folders (.git, .venv, node_modules, caches) and files that are not UTF-8 text or larger than
  MAX_BYTES are not read;
- text is written as UTF-8 with \n line endings, through a temporary file and a rename.
"""

import os
from pathlib import Path, PurePosixPath

from wings.domain.errors import InvalidInputError
from wings.domain.sync import IGNORED_DIRS, IGNORED_FILES

MAX_BYTES = 1_000_000
MAX_FILES = 5_000


class LocalProjectFolder:
    def __init__(self, forbidden: list[Path] | None = None, home: Path | None = None, projects_dir: Path | None = None):
        self._forbidden = [p.resolve() for p in (forbidden or [])]
        self._home = (home or Path.home()).resolve()
        self._projects_dir = projects_dir.expanduser().resolve() if projects_dir is not None else None

    # Choosing the folder

    def default_path(self, name: str) -> str | None:
        if self._projects_dir is None or not name or name in (".", "..") or any(c in name for c in "/\\:"):
            return None
        return str(self._projects_dir / name)

    def same(self, a: str, b: str) -> bool:
        """`C:/x` and `c:/x/` are one folder: compared resolved, and without case where the system ignores it."""
        return os.path.normcase(self._root(a)) == os.path.normcase(self._root(b))

    def is_empty(self, path: str) -> bool:
        root = self._root(path)
        if not root.exists():
            return True
        if not root.is_dir():
            return False
        try:
            with os.scandir(root) as entries:
                return all(e.name == ".git" or e.name in IGNORED_FILES or e.name.startswith(".wings-") for e in entries)
        except OSError:
            return False  # cannot look inside: do not claim it is free

    def problem(self, path: str) -> str | None:
        raw = (path or "").strip()
        if not raw:
            return "Give the full path of a folder, for example C:\\Projects\\todo-app."
        folder = Path(raw).expanduser()
        if not folder.is_absolute():
            return f"'{raw}' is not a full path. Give it from the drive or the root, for example C:\\Projects\\todo-app."
        folder = folder.resolve()
        if folder == Path(folder.anchor) or folder == self._home:
            return f"'{folder}' is too broad. Choose a folder for this project, for example {self._home / 'Projects' / 'todo-app'}."
        for own in self._forbidden:
            if folder == own or folder.is_relative_to(own) or own.is_relative_to(folder):
                return f"'{folder}' overlaps the tool's own files ({own}). Choose a folder outside it."
        if folder.exists() and not folder.is_dir():
            return f"'{folder}' is a file, not a folder."
        if not folder.exists() and not folder.parent.is_dir() and folder.parent != self._projects_dir:
            return f"'{folder.parent}' does not exist. Create it first or choose another place."
        return None

    def prepare(self, path: str) -> None:
        problem = self.problem(path)
        if problem:
            raise InvalidInputError(problem)
        folder = self._root(path)
        try:
            folder.mkdir(parents=folder.parent == self._projects_dir, exist_ok=True)
            probe = folder / ".wings-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as err:
            raise InvalidInputError(f"Cannot write to '{folder}': {err.strerror or err}.") from err

    # Files

    def exists(self, path: str) -> bool:
        return self._root(path).is_dir()

    def read_files(self, path: str) -> dict[str, str]:
        root = self._root(path)
        found: dict[str, str] = {}
        if not root.is_dir():
            return found
        for current, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS and not d.startswith("."))
            for name in sorted(files):
                if name in IGNORED_FILES or name.startswith(".wings-"):
                    continue
                file = Path(current) / name
                if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_BYTES:
                    continue
                try:
                    text = file.read_bytes().decode("utf-8")
                except (OSError, UnicodeDecodeError):
                    continue  # binary or unreadable: not something Wings wrote or can import
                found[file.relative_to(root).as_posix()] = text
                if len(found) >= MAX_FILES:
                    return found
        return found

    def write_file(self, path: str, rel: str, text: str) -> None:
        target = self._inside(path, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".wings-{target.name}.tmp")
        tmp.write_bytes(text.encode("utf-8"))
        os.replace(tmp, target)

    def delete_file(self, path: str, rel: str) -> None:
        root, target = self._root(path), self._inside(path, rel)
        target.unlink(missing_ok=True)
        parent = target.parent
        while parent != root and parent.is_relative_to(root):
            try:
                parent.rmdir()  # only succeeds when empty
            except OSError:
                break
            parent = parent.parent

    # Internals

    def _root(self, path: str) -> Path:
        return Path(path.strip()).expanduser().resolve()

    def _inside(self, path: str, rel: str) -> Path:
        root = self._root(path)
        p = PurePosixPath(rel)
        bad = not rel or "\\" in rel or p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0])
        target = (root / Path(*p.parts)).resolve() if not bad else root
        if bad or not target.is_relative_to(root) or target == root:
            raise ValueError(f"'{rel}' is not a file inside the project folder.")
        return target
