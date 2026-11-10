"""Data shapes of the deployment wing."""

import shlex
from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator, model_validator

from wings.domain.project import slugify


def deploy_id(path: str) -> str:
    """The artifact id of a file. Different paths can map to one id (todo/__main__.py, todo/main.py);
    the output schemas refuse such sets, so no file silently replaces another."""
    return "deploy-" + slugify(path.replace("/", "-").replace(".", "-"))


def same_ids(paths: list[str]) -> list[str]:
    ids = [deploy_id(p) for p in paths]
    return sorted({p for p, i in zip(paths, ids) if ids.count(i) > 1})


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
    smoke_command: str = Field(description="A short command that proves the program starts, e.g. python -m todo list. Run without a shell: no pipes or redirection")
    smoke_input: str = Field("", description="Text the program reads from standard input during the smoke run, for interactive programs, e.g. \"0 0\nq\n\" for one move and quit; empty for none")
    files: list[DeployFile] = Field(min_length=1, description="The complete set of files, also when revising: a file left out is removed")

    @field_validator("smoke_command")
    @classmethod
    def _python(cls, cmd: str) -> str:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        if any(set(token) <= set("|&;<>") for token in lexer):  # operators outside quotes only
            raise ValueError(
                "smoke_command runs without a shell, so pipes and redirection do not work; "
                "give the command alone (python -m <package> ...) and put what an interactive program reads into smoke_input"
            )
        parts = shlex.split(cmd)
        if not parts or parts[0] not in ("python", "python3"):
            raise ValueError("smoke_command must start with python, e.g. python -m todo list")
        return cmd.strip()

    @model_validator(mode="after")
    def _distinct_ids(self) -> "DeployerOutput":
        clash = same_ids([f.path for f in self.files])
        if clash:
            raise ValueError(f"these paths would be stored as the same file, rename one: {', '.join(clash)}")
        return self

