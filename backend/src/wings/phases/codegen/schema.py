"""Data shapes of the code generation wing."""

import ast
from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator, model_validator

from wings.domain.project import slugify

ALLOWED_SUFFIXES = {".py", ".txt", ".md", ".toml", ".cfg", ".json"}


def file_id(path: str) -> str:
    """The artifact id of a file. Different paths can map to one id (todo/__main__.py, todo/main.py);
    the output schemas refuse such sets, so no file silently replaces another."""
    return "source-" + slugify(path.replace("/", "-").replace(".", "-"))


def same_ids(paths: list[str]) -> list[str]:
    ids = [file_id(p) for p in paths]
    return sorted({p for p, i in zip(paths, ids) if ids.count(i) > 1})


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
    files: list[SourceFile] = Field(min_length=1, description="The complete set of files, also when revising: a file left out is removed")

    @model_validator(mode="after")
    def _unique(self) -> "CoderOutput":
        paths = [f.path for f in self.files]
        dupes = sorted({p for p in paths if paths.count(p) > 1})
        if dupes:
            raise ValueError(f"duplicate file paths: {', '.join(dupes)}")
        return self

    @model_validator(mode="after")
    def _distinct_ids(self) -> "CoderOutput":
        clash = same_ids([f.path for f in self.files])
        if clash:
            raise ValueError(f"these paths would be stored as the same file, rename one: {', '.join(clash)}")
        return self

