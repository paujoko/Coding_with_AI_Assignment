"""Filesystem implementation of the ArtifactStore port.

Layout of one workspace (one showcase project):

    <root>/<project_id>/
        project.json              phase states
        events.jsonl              activity log, append-only
        messages.jsonl            conversation, append-only
        artifacts/<id>/r0001.json every revision of every artifact
        files/<path>              latest human-readable version (requirements.md, design/*.puml ...)

Plain files on purpose: diffable, inspectable in the demo, no database to run.
"""

import json
import re
import threading
from pathlib import Path, PurePosixPath

from wings.domain.activity import Event, Message
from wings.domain.artifacts import Artifact
from wings.domain.errors import NotFoundError
from wings.domain.phases import PhaseId
from wings.domain.project import Project

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _check_id(value: str, what: str) -> str:
    if not _SAFE_ID.match(value):
        raise ValueError(f"Unsafe {what} '{value}'.")
    return value


class FileSystemStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # Projects

    def _dir(self, project_id: str) -> Path:
        return self.root / _check_id(project_id, "project id")

    def project_exists(self, project_id: str) -> bool:
        return (self._dir(project_id) / "project.json").exists()

    def save_project(self, project: Project) -> None:
        with self._lock:
            d = self._dir(project.id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "project.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")

    def load_project(self, project_id: str) -> Project:
        try:
            path = self._dir(project_id) / "project.json"
        except ValueError:
            raise NotFoundError(f"Unknown project '{project_id}'.") from None
        if not path.exists():
            raise NotFoundError(f"Unknown project '{project_id}'.")
        return Project.model_validate_json(path.read_text(encoding="utf-8"))

    def list_projects(self) -> list[Project]:
        projects = [Project.model_validate_json(p.read_text(encoding="utf-8")) for p in self.root.glob("*/project.json")]
        return sorted(projects, key=lambda p: p.created_at)

    # Artifacts

    def _artifact_dir(self, project_id: str, artifact_id: str) -> Path:
        return self._dir(project_id) / "artifacts" / _check_id(artifact_id, "artifact id")

    def save_artifact(self, project_id: str, artifact: Artifact) -> Artifact:
        with self._lock:
            d = self._artifact_dir(project_id, artifact.id)
            d.mkdir(parents=True, exist_ok=True)
            saved = artifact.model_copy(update={"revision": len(list(d.glob("r*.json"))) + 1})
            (d / f"r{saved.revision:04d}.json").write_text(saved.model_dump_json(indent=2), encoding="utf-8")
            if saved.path and saved.text is not None:
                target = self._materialized(project_id, saved.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(saved.text, encoding="utf-8")
            return saved

    def _materialized(self, project_id: str, rel: str) -> Path:
        pure = PurePosixPath(rel)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"Artifact path must stay inside the workspace: '{rel}'.")
        return self._dir(project_id) / "files" / Path(*pure.parts)

    def artifact_history(self, project_id: str, artifact_id: str) -> list[Artifact]:
        try:
            d = self._artifact_dir(project_id, artifact_id)
        except ValueError:
            raise NotFoundError(f"Unknown artifact '{artifact_id}'.") from None
        revisions = sorted(d.glob("r*.json"))
        if not revisions:
            raise NotFoundError(f"Unknown artifact '{artifact_id}' in project '{project_id}'.")
        return [Artifact.model_validate_json(p.read_text(encoding="utf-8")) for p in revisions]

    def get_artifact(self, project_id: str, artifact_id: str) -> Artifact:
        return self.artifact_history(project_id, artifact_id)[-1]

    def list_artifacts(self, project_id: str, phase: PhaseId | None = None) -> list[Artifact]:
        base = self._dir(project_id) / "artifacts"
        latest = [self.get_artifact(project_id, d.name) for d in sorted(base.glob("*")) if d.is_dir()] if base.exists() else []
        return [a for a in latest if phase is None or a.phase == phase]

    # Messages and events (JSON lines, append-only)

    def _append(self, path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _read_lines(self, path: Path) -> list[str]:
        return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()] if path.exists() else []

    def append_message(self, project_id: str, message: Message) -> None:
        with self._lock:
            self._append(self._dir(project_id) / "messages.jsonl", message.model_dump_json())

    def list_messages(self, project_id: str, phase: PhaseId | None = None) -> list[Message]:
        msgs = [Message.model_validate_json(ln) for ln in self._read_lines(self._dir(project_id) / "messages.jsonl")]
        return [m for m in msgs if phase is None or m.phase == phase]

    def append_event(self, project_id: str, event: Event) -> Event:
        with self._lock:
            path = self._dir(project_id) / "events.jsonl"
            lines = self._read_lines(path)
            last = json.loads(lines[-1])["seq"] if lines else 0
            saved = event.model_copy(update={"seq": last + 1})
            self._append(path, saved.model_dump_json())
            return saved

    def list_events(self, project_id: str, after: int = 0) -> list[Event]:
        events = [Event.model_validate_json(ln) for ln in self._read_lines(self._dir(project_id) / "events.jsonl")]
        return [e for e in events if e.seq > after]
