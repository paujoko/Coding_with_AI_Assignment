"""Data shapes of the deployment wing."""

import shlex
from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator, model_validator

from wings.domain.project import slugify


RUN_GUIDE_FILE = "RUN.md"  # written by code from the run guide, next to DEPLOY.md


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
        if str(p).lower() == RUN_GUIDE_FILE.lower():
            raise ValueError(f"{RUN_GUIDE_FILE} is written by the tool from start_command; leave it out and put run notes into DEPLOY.md")
        return str(p)


def _python_command(cmd: str, field: str, example: str) -> str:
    """A command Wings can read and check: python first, no shell operators outside quotes."""
    try:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        operators = any(set(token) <= set("|&;<>") for token in lexer)
        parts = shlex.split(cmd)
    except ValueError as err:
        raise ValueError(f"{field} cannot be read as a command ({err}), e.g. {example}") from err
    if operators:
        raise ValueError(
            f"{field} runs without a shell, so pipes and redirection do not work; "
            "give the command alone (python -m <package> ...) and put what an interactive program reads into smoke_input"
        )
    if not parts or parts[0] not in ("python", "python3"):
        raise ValueError(f"{field} must start with python, e.g. {example}")
    return cmd.strip()


class DeployerOutput(BaseModel):
    notes: str = Field(description="At most two short sentences (about 40 words): what was set up and the one thing to check by hand. No commands, no file contents")
    start_command: str = Field(
        "",
        description="The command the developer types in the project folder to start the program for real, without Docker, "
        "e.g. python -m todo or python -m shop --port 8000. Never the check option of the smoke run",
    )
    url: str | None = Field(None, description="For a web app: the address to open after starting, e.g. http://127.0.0.1:8000/; null for a command-line program")
    example_commands: list[str] = Field(default_factory=list, description="For a command-line program: up to 3 commands to try, e.g. python -m todo list; empty for a web app")
    stop_hint: str = Field("", description="How to stop a program that keeps running, e.g. Ctrl+C; empty when every command ends by itself")
    smoke_command: str = Field(description="A short command that proves the program starts, e.g. python -m todo list. Run without a shell: no pipes or redirection")
    smoke_input: str = Field("", description="Text the program reads from standard input during the smoke run, for interactive programs, e.g. \"0 0\nq\n\" for one move and quit; empty for none")
    files: list[DeployFile] = Field(min_length=1, description="The complete set of files, also when revising: a file left out is removed")

    @field_validator("smoke_command")
    @classmethod
    def _python(cls, cmd: str) -> str:
        return _python_command(cmd, "smoke_command", "python -m todo list")

    @field_validator("start_command")
    @classmethod
    def _start(cls, cmd: str) -> str:
        """Empty is allowed (code then derives the command from the smoke command); a wrong form is sent back."""
        return _python_command(cmd, "start_command", "python -m todo") if cmd.strip() else ""

    @model_validator(mode="after")
    def _distinct_ids(self) -> "DeployerOutput":
        clash = same_ids([f.path for f in self.files])
        if clash:
            raise ValueError(f"these paths would be stored as the same file, rename one: {', '.join(clash)}")
        return self

