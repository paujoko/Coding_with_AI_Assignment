"""Data shapes of the code generation wing."""

import ast
from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_SUFFIXES = {".py", ".txt", ".md", ".toml", ".cfg", ".json"}


def check_relative_path(path: str) -> str:
    p = PurePosixPath(path)
    if not path or "\\" in path or p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0]):
        raise ValueError(f"'{path}' must be a relative path with forward slashes and no '..'")
    return path


class SourceFile(BaseModel):
    path: str = Field(description="Relative path with forward slashes, e.g. todo/service.py")
    purpose: str = Field(description="One line: what the file is for and which design element it implements")
    covers: list[str] = Field(default_factory=list, description="REQ ids this file implements")
    content: str = Field(description="The complete file content")

    @field_validator("path")
    @classmethod
    def _path(cls, path: str) -> str:
        path = check_relative_path(path.strip())
        if PurePosixPath(path).suffix not in ALLOWED_SUFFIXES:
            raise ValueError(f"'{path}': only {', '.join(sorted(ALLOWED_SUFFIXES))} files")
        return path

    @model_validator(mode="after")
    def _parses(self) -> "SourceFile":
        if self.path.endswith(".py"):
            try:
                ast.parse(self.content, filename=self.path)
            except SyntaxError as err:
                raise ValueError(f"{self.path} line {err.lineno}: {err.msg}") from err
        return self


class CoderOutput(BaseModel):
    notes: str = Field(description="What was generated and how it maps to the design; open points")
    run: str = Field(description="How to run the program, e.g. python -m todo list")
    files: list[SourceFile] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "CoderOutput":
        paths = [f.path for f in self.files]
        dupes = sorted({p for p in paths if paths.count(p) > 1})
        if dupes:
            raise ValueError(f"duplicate file paths: {', '.join(dupes)}")
        return self
