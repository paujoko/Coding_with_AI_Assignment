"""Data shapes of the testing wing."""

import ast
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from wings.domain.project import slugify


def test_file_id(path: str) -> str:
    """The artifact id of a file. Different paths can map to one id (todo/__main__.py, todo/main.py);
    the output schemas refuse such sets, so no file silently replaces another."""
    return "test-" + slugify(path.removeprefix("tests/").replace("/", "-").replace(".", "-"))


test_file_id.__test__ = False  # type: ignore[attr-defined]  # not a pytest test


def same_ids(paths: list[str]) -> list[str]:
    ids = [test_file_id(p) for p in paths]
    return sorted({p for p, i in zip(paths, ids) if ids.count(i) > 1})


class TestFile(BaseModel):
    __test__ = False

    path: str = Field(description="Under tests/, e.g. tests/test_tasks.py")
    purpose: str = Field(description="One line: which requirements and scenarios the file checks")
    covers: list[str] = Field(default_factory=list, description="REQ ids the tests check")
    content: str = Field(description="The complete pytest file")

    @field_validator("path")
    @classmethod
    def _path(cls, path: str) -> str:
        p = PurePosixPath(path.strip())
        if p.is_absolute() or ".." in p.parts or "\\" in path or not p.parts or p.parts[0] != "tests" or p.suffix != ".py":
            raise ValueError(f"'{path}' must be a .py file under tests/")
        return str(p)

    @model_validator(mode="after")
    def _parses(self) -> "TestFile":
        try:
            ast.parse(self.content, filename=self.path)
        except SyntaxError as err:
            raise ValueError(f"{self.path} line {err.lineno}: {err.msg}") from err
        return self


class TesterOutput(BaseModel):
    notes: str = Field(description="What the tests check and what they do not")
    files: list[TestFile] = Field(min_length=1, description="The complete set of files, also when revising: a file left out is removed")

    @model_validator(mode="after")
    def _distinct_ids(self) -> "TesterOutput":
        clash = same_ids([f.path for f in self.files])
        if clash:
            raise ValueError(f"these paths would be stored as the same file, rename one: {', '.join(clash)}")
        return self


class DebuggerOutput(BaseModel):
    diagnosis: str = Field(description="Why the tests fail, in plain words, naming the test and the line of code or test")
    cause: Literal["code", "test", "environment"] = Field(description="Where the mistake is")
    fix: str = Field(description="The change that makes the tests pass, precise enough to hand to the developer agent")
    test_files: list[TestFile] = Field(default_factory=list, description="Only when cause is 'test': the corrected test files")
