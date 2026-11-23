"""Deployment, checked by code: does the Dockerfile copy what exists and start what is there, and
does the command that starts the program without Docker (the run guide) name something the code has?"""

import re
import shlex
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_COPY = re.compile(r"^\s*(?:COPY|ADD)\s+(?:--\S+\s+)*(.+?)\s*$", re.IGNORECASE)
_MODULE = re.compile(r"python[0-9.]*\"?\s*,?\s*\"?-m\"?\s*,?\s*\"?([A-Za-z_][\w.]*)")
_PYTHON = re.compile(r"^(?:python[0-9.]*|py)(?:\.exe)?$")

# Options that make a program start, prove it works and exit: right for a smoke run, wrong for the developer's start.
CHECK_FLAGS = frozenset({"--check", "--smoke", "--smoke-test", "--self-test", "--selftest", "--dry-run"})
MAX_EXAMPLES = 3


def _exists(src: str, paths: set[str]) -> bool:
    src = src.strip().strip('"').rstrip("/")
    if src in ("", "."):
        return True
    return src in paths or any(p.startswith(src + "/") for p in paths)


def modules_started(text: str) -> list[str]:
    """Modules started with `python -m X` in a Dockerfile or a script."""
    return list(dict.fromkeys(_MODULE.findall(text)))


def _module_exists(module: str, code_paths: set[str], paths: set[str]) -> bool:
    packages = {p.split("/")[0] for p in code_paths if p.endswith("__main__.py")}
    return module.split(".")[0] in packages or f"{module.replace('.', '/')}.py" in paths


class RunTarget(BaseModel):
    """What a `python ...` command starts: a module (`python -m todo`) or a script (`python app.py`)."""

    kind: Literal["module", "script"]
    name: str


def run_target(command: str) -> RunTarget | None:
    """The module or script a command starts; None when it is not a python command of that form
    (another program, `python -c ...`, a shell line Wings cannot read)."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts or not _PYTHON.match(parts[0]):
        return None
    for i, part in enumerate(parts[1:], start=1):
        if part == "-m":
            return RunTarget(kind="module", name=parts[i + 1]) if i + 1 < len(parts) else None
        if part == "-c":
            return None
        if not part.startswith("-"):
            return RunTarget(kind="script", name=part) if part.endswith(".py") else None
    return None


def command_problems(command: str, code_paths: set[str], deploy_paths: Iterable[str] = (), what: str = "The start command") -> list[str]:
    """Why a command the developer is told to type would not start the program."""
    target = run_target(command)
    paths = set(code_paths) | set(deploy_paths)
    if target is None:
        return [f"{what} `{command}` is not `python -m <package>` or `python <file>.py`, so Wings cannot check that it starts the program."]
    if target.kind == "module" and not _module_exists(target.name, set(code_paths), paths):
        return [f"{what} `{command}` starts 'python -m {target.name}', but the code has no such module."]
    if target.kind == "script" and target.name.replace("\\", "/").removeprefix("./") not in paths:
        return [f"{what} `{command}` runs '{target.name}', which is not in the project."]
    return []


def _quote(part: str) -> str:
    """Double quotes where needed: they work in PowerShell, cmd and POSIX shells alike."""
    return '"' + part.replace('"', '\\"') + '"' if not part or re.search(r"\s|\"", part) else part


def derive_start_command(smoke_command: str) -> str:
    """A start command for projects whose deployer gave none: the smoke command without its check
    option (`python -m shop --check` -> `python -m shop`). Empty when the smoke command does not start a
    module or a script (`python -c ...`), because then nothing safe can be derived."""
    if run_target(smoke_command) is None:
        return ""
    parts = shlex.split(smoke_command)
    if not any(p in CHECK_FLAGS for p in parts):
        return smoke_command.strip()
    return " ".join(_quote(p) for p in parts if p not in CHECK_FLAGS)


class RunGuide(BaseModel):
    """How the developer starts the generated program from the project folder, as data (artifact
    `run-guide`). The folder itself is not part of it; whoever shows the guide knows the project's folder."""

    start_command: str = ""  # e.g. python -m todo; empty when none is known
    url: str | None = None  # for a web app: where to open it
    example_commands: list[str] = Field(default_factory=list)  # for a command-line program, at most three
    stop_hint: str = ""  # e.g. Ctrl+C
    checked: bool = False  # the smoke run of the same module or script passed and the command names existing code
    derived: bool = False  # the start command was derived from the smoke command by code, not given by the deployer

    @field_validator("start_command", "stop_hint", mode="before")
    @classmethod
    def _text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else "" if value is None else value

    @field_validator("url", mode="before")
    @classmethod
    def _url(cls, value: object) -> object:
        url = value.strip() if isinstance(value, str) else None
        return url if url and url.startswith(("http://", "https://")) else None

    @field_validator("example_commands", mode="before")
    @classmethod
    def _examples(cls, value: object) -> object:
        if not isinstance(value, list):
            return []
        return [v.strip() for v in value if isinstance(v, str) and v.strip()][:MAX_EXAMPLES]

    def markdown(self) -> str:
        lines = ["# Run it", ""]
        if not self.start_command:
            lines += ["No start command is known. See DEPLOY.md for how to run the program."]
            return "\n".join(lines) + "\n"
        lines += ["From the project folder, with Python 3.12 and without Docker:", "", "```", self.start_command, "```", ""]
        if self.checked:
            lines += ["Checked by Wings: the smoke run of this program started and exited cleanly.", ""]
        else:
            lines += ["Not checked: the last deployment check did not confirm that this command starts the program.", ""]
        if self.url:
            lines += [f"Then open {self.url} in the browser.", ""]
        if self.example_commands:
            lines += ["Examples:", "", "```", *self.example_commands, "```", ""]
        if self.stop_hint:
            lines += [f"Stop: {self.stop_hint}", ""]
        lines += ["Start scripts and Docker: see DEPLOY.md."]
        return "\n".join(lines) + "\n"


def guide_checked(guide: RunGuide, smoke_command: str, smoke_passed: bool, code_paths: set[str], deploy_paths: Iterable[str] = ()) -> bool:
    """True when the passed smoke run started the same module or script as the start command, and
    that command names code that exists."""
    target = run_target(guide.start_command)
    if not smoke_passed or target is None or target != run_target(smoke_command):
        return False
    return not command_problems(guide.start_command, code_paths, deploy_paths)


def check_deployment(deploy_files: dict[str, str], code_paths: set[str], guide: RunGuide | None = None) -> list[str]:
    """Problems a reader could find by looking: missing Dockerfile parts, copies of files that do not exist,
    modules started that the code does not contain, and a run guide whose commands start nothing."""
    problems: list[str] = []
    paths = set(code_paths) | set(deploy_files)
    dockerfile = next((t for p, t in deploy_files.items() if p.split("/")[-1] == "Dockerfile"), None)
    if dockerfile is not None:
        lines = [line for line in dockerfile.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not any(line.strip().upper().startswith("FROM ") for line in lines):
            problems.append("Dockerfile: no FROM line.")
        if not any(line.strip().upper().startswith(("CMD", "ENTRYPOINT")) for line in lines):
            problems.append("Dockerfile: no CMD or ENTRYPOINT, the container would not start the program.")
        for line in lines:
            m = _COPY.match(line)
            if m:
                parts = shlex.split(m.group(1).replace("[", " ").replace("]", " ").replace(",", " "))
                for src in parts[:-1]:
                    if not _exists(src, paths):
                        problems.append(f"Dockerfile copies '{src}', which is not in the project.")
    for path, text in deploy_files.items():
        for module in modules_started(text):
            if not _module_exists(module, code_paths, paths):
                problems.append(f"{path} starts 'python -m {module}', but the code has no such module.")
    if guide is not None:
        if guide.start_command:
            problems += command_problems(guide.start_command, code_paths, deploy_files)
            flags = sorted(CHECK_FLAGS & set(guide.start_command.split()))
            if flags:
                problems.append(f"The start command `{guide.start_command}` has the check option {flags[0]}: the program would start, check itself and exit.")
        for example in guide.example_commands:
            if run_target(example) is not None:  # other examples (curl ...) cannot be checked and are left alone
                problems += command_problems(example, code_paths, deploy_files, what="The example")
    return list(dict.fromkeys(problems))
