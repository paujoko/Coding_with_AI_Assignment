"""Data shapes of the deployment wing."""

import shlex
from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator


class DeployFile(BaseModel):
    path: str = Field(description="Relative path, e.g. Dockerfile, run.sh, run.ps1, DEPLOY.md")
    purpose: str = Field(description="One line: what the file is for")
    content: str = Field(description="The complete file content")

    @field_validator("path")
    @classmethod
    def _path(cls, path: str) -> str:
        p = PurePosixPath(path.strip())
        if not path.strip() or p.is_absolute() or ".." in p.parts or "\\" in path:
            raise ValueError(f"'{path}' must be a relative path with forward slashes and no '..'")
        return str(p)


class DeployerOutput(BaseModel):
    notes: str = Field(description="How the software is deployed and run, and what to check by hand")
    smoke_command: str = Field(description="A short command that proves the program starts, e.g. python -m todo list")
    files: list[DeployFile] = Field(min_length=1)

    @field_validator("smoke_command")
    @classmethod
    def _python(cls, cmd: str) -> str:
        parts = shlex.split(cmd)
        if not parts or parts[0] not in ("python", "python3"):
            raise ValueError("smoke_command must start with python, e.g. python -m todo list")
        return cmd.strip()
