"""Two-way sync between the artifacts and the developer's output folder, decided by code (ADR 0015).

Layout of the folder: the program at the top (what the workspace keeps under `app/`: code, tests,
Dockerfile, start scripts), everything else under `docs/wings/` (requirements.md, design/*.puml,
refinement/*.puml, reports/). So the folder is a normal project the developer opens in an editor.

Two directions:
- Wings -> folder (`plan_export`): after every change Wings writes the current files. A file the
  developer changed or deleted by hand is never overwritten or restored; it stays until they decide.
- folder -> Wings (`folder_changes`): files that differ from what Wings last wrote are hand edits. The
  orchestrator offers them for import as new artifact revisions (author: developer), after which the
  usual staleness rules and the design-versus-code check apply.

Line endings do not count as a change: editors on Windows often write \r\n.
"""

import hashlib
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field

from wings.domain.artifacts import Artifact, ArtifactKind
from wings.domain.folder import SyncedFile
from wings.domain.phases import PhaseId

APP_PREFIX = "app/"
DOCS_PREFIX = "docs/wings/"

# Never read: tool and editor folders, caches, virtual environments.
IGNORED_DIRS = frozenset({".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode", "dist", "build"})
IGNORED_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})

# A hand edit of these kinds can become a new revision; the others are computed or structured by Wings.
EDITABLE_KINDS = frozenset({ArtifactKind.SOURCE_FILE, ArtifactKind.TEST_FILE, ArtifactKind.DEPLOYMENT_FILE, ArtifactKind.DIAGRAM})
# Deleting one of these by hand can be taken over (the artifact is retired).
RETIRABLE_KINDS = frozenset({ArtifactKind.SOURCE_FILE, ArtifactKind.TEST_FILE})
# A new file of these types in the program part of the folder is offered for import. Data files the
# program writes while it runs (tasks.json, a SQLite database) are not code and are left alone.
ADOPTABLE_SUFFIXES = frozenset({".py", ".html", ".css", ".js"})

ChangeKind = Literal["modified", "added", "deleted"]


def normalized(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()


def folder_path(artifact_path: str) -> str:
    """Where an artifact's file goes in the developer's folder."""
    if artifact_path.startswith(APP_PREFIX):
        return artifact_path[len(APP_PREFIX) :]
    return DOCS_PREFIX + artifact_path


def program_path(path: str) -> str | None:
    """The path inside the program (as the code and test wings name files), None for Wings' documents."""
    return None if path.startswith(DOCS_PREFIX) else path


def is_ignored(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(p in IGNORED_DIRS for p in parts[:-1]) or (bool(parts) and parts[-1] in IGNORED_FILES)


class FolderChange(BaseModel):
    """A file in the folder that differs from what Wings last wrote there."""

    path: str  # folder-relative, forward slashes
    change: ChangeKind
    artifact_id: str | None = None  # None for a new file
    phase: PhaseId | None = None
    importable: bool = False
    newer_in_wings: bool = False  # Wings made a newer revision since: importing replaces it, restoring loses the edit
    note: str = ""


class FolderStatus(BaseModel):
    path: str | None
    exists: bool = True
    changes: list[FolderChange] = Field(default_factory=list)
    problem: str | None = None  # why the folder cannot be read or written right now


class ExportPlan(BaseModel):
    writes: dict[str, str] = Field(default_factory=dict)  # folder path -> text
    deletes: list[str] = Field(default_factory=list)  # files Wings wrote whose artifact is gone and that nobody changed
    kept: list[str] = Field(default_factory=list)  # changed or deleted by hand: left alone
    files: dict[str, SyncedFile] = Field(default_factory=dict)  # the manifest after the plan is carried out


def wanted_files(artifacts: list[Artifact]) -> dict[str, Artifact]:
    """Folder path -> the artifact whose text belongs there (latest, not retired, with a file)."""
    return {folder_path(a.path): a for a in artifacts if not a.retired and a.path and a.text is not None}


def plan_export(artifacts: list[Artifact], manifest: dict[str, SyncedFile], on_disk: dict[str, str]) -> ExportPlan:
    """What to write and delete so the folder shows the current artifacts, without touching hand edits."""
    plan = ExportPlan()
    wanted = wanted_files(artifacts)
    for path, artifact in sorted(wanted.items()):
        text = artifact.text or ""
        stamp = SyncedFile(artifact_id=artifact.id, revision=artifact.revision, sha256=fingerprint(text))
        disk, before = on_disk.get(path), manifest.get(path)
        if disk is not None and fingerprint(disk) == stamp.sha256:
            plan.files[path] = stamp  # already there (also after an import)
        elif disk is not None and (before is None or fingerprint(disk) != before.sha256):
            plan.kept.append(path)  # changed by hand, or there before Wings wrote it
            if before is not None:
                plan.files[path] = before
        elif disk is None and before is not None:
            plan.kept.append(path)  # deleted by hand: not restored behind the developer's back
            plan.files[path] = before
        else:
            plan.writes[path] = text
            plan.files[path] = stamp
    for path, before in sorted(manifest.items()):
        if path in wanted:
            continue
        disk = on_disk.get(path)
        if disk is not None and fingerprint(disk) == before.sha256:
            plan.deletes.append(path)
        elif disk is not None:
            plan.kept.append(path)  # the artifact is gone but the developer changed the file: theirs now
    return plan


def folder_changes(artifacts: list[Artifact], manifest: dict[str, SyncedFile], on_disk: dict[str, str]) -> list[FolderChange]:
    """Hand edits, hand deletions and new code files, before anyone decided what to do with them.
    `importable` here is about the kind of file only; the orchestrator asks the wings about the content."""
    changes: list[FolderChange] = []
    wanted = wanted_files(artifacts)
    for path, artifact in sorted(wanted.items()):
        disk, before = on_disk.get(path), manifest.get(path)
        if disk is None:
            if before is not None:
                ok = artifact.kind in RETIRABLE_KINDS
                note = "Deleted in the folder." if ok else "Deleted in the folder; the project still needs this file. Restore it."
                changes.append(FolderChange(path=path, change="deleted", artifact_id=artifact.id, phase=artifact.phase, importable=ok, newer_in_wings=artifact.revision != before.revision, note=note))
            continue
        current = fingerprint(disk)
        if current == fingerprint(artifact.text or ""):
            continue
        if before is not None and current == before.sha256:
            continue  # unchanged since Wings wrote it; the export brings the newer revision
        ok = artifact.kind in EDITABLE_KINDS
        if ok:
            note = "Changed in the folder."
        elif artifact.kind is ArtifactKind.REQUIREMENTS:
            note = "Requirements are edited in the step Requirements; restore the file."
        else:
            note = "Computed by code; restore the file."
        newer = before is None or artifact.revision != before.revision
        changes.append(FolderChange(path=path, change="modified", artifact_id=artifact.id, phase=artifact.phase, importable=ok, newer_in_wings=newer, note=note))
    for path in sorted(on_disk):
        if path in wanted or path in manifest or is_ignored(path):
            continue
        if program_path(path) is not None and PurePosixPath(path).suffix in ADOPTABLE_SUFFIXES:
            changes.append(FolderChange(path=path, change="added", note="New in the folder."))
    return changes
