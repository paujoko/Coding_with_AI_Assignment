"""The developer's output folder: where on their computer a project's files live (ADR 0015).

Only the state kept in the project lives here: the folder and, per file Wings wrote, which artifact
revision it came from and a fingerprint of the text. The rules that compare it with the folder are
in `domain/sync.py`; reading and writing the folder is the `ProjectFolder` port.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SyncedFile(BaseModel):
    """A file as Wings last wrote it (or last took it over from the developer)."""

    artifact_id: str
    revision: int
    sha256: str  # of the text with line endings normalized to \n


class OutputFolder(BaseModel):
    path: str  # absolute path on the developer's computer
    files: dict[str, SyncedFile] = Field(default_factory=dict)  # folder-relative POSIX path -> what Wings wrote there
    synced_at: datetime | None = None
