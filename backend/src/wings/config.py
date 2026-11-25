"""Settings from environment variables and the `.env` file at the repository root.

Precedence: real environment variables, then `.env`, then the defaults below. `.env` is
read at start (no manual `export` or `set` needed, also on Windows) and written by the
Settings page of the UI. It is git-ignored; `.env.example` lists every variable.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_MOCK_SCRIPT = Path(__file__).resolve().parent / "adapters" / "mock_scripts" / "demo_todo.json"
TOOLS_DIR = REPO_ROOT / "tools"  # git-ignored; Settings can download plantuml.jar here
PUBLIC_PLANTUML_SERVER = "https://www.plantuml.com/plantuml"

PROVIDERS = ("mock", "openai", "openrouter", "anthropic")
TIERS = ("small", "mid", "frontier")
EFFORTS = ("low", "medium", "high", "xhigh", "max")  # Claude only (output_config.effort); unset: the model's default

# Models per agent tier. Each agent names its tier in its wing (phases/*/module.py); see docs/code/llm.md.
# Check the current model names with your provider; they can be changed in Settings.
DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "openai": {"small": "gpt-5-nano", "mid": "gpt-5-mini", "frontier": "gpt-5"},
    # The course's model since 2026-11-09 (the only one its OpenRouter keys may use); one model for all tiers.
    "openrouter": {
        "small": "deepseek/deepseek-v4.1-flash-1017",
        "mid": "deepseek/deepseek-v4.1-flash-1017",
        "frontier": "deepseek/deepseek-v4.1-flash-1017",
    },
    # Claude with the developer's own Anthropic key. Ids from Anthropic's model docs (2026-11-03).
    "anthropic": {"small": "claude-haiku-5-5", "mid": "claude-sonnet-5-5", "frontier": "claude-sonnet-5-5"},
}

KEY_VARIABLE = {"openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def read_env_file(path: Path) -> dict[str, str]:
    """KEY=value lines; blank lines and # comments are skipped; surrounding quotes are removed."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def write_env_file(path: Path, updates: dict[str, str | None]) -> None:
    """Set (or with None remove) variables, keeping every other line and comment as it was."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(updates)
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in pending:
            value = pending.pop(key)
            if value is not None:
                out.append(f"{key}={value}")
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in pending.items() if v is not None]
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _found_jar() -> Path | None:
    """A plantuml.jar downloaded by Settings into tools/ is used without configuration."""
    jar = TOOLS_DIR / "plantuml.jar"
    return jar if jar.exists() else None


def _jar(configured: str | None) -> Path | None:
    """The configured PLANTUML_JAR if that file exists. A stale path (the folder was moved) must not
    switch diagrams off while tools/plantuml.jar is there, so then the found one is used."""
    if configured and configured.strip() and Path(configured.strip()).expanduser().is_file():
        return Path(configured.strip()).expanduser()
    return _found_jar()


def _seconds(raw: str) -> float:
    """WINGS_MOCK_DELAY as seconds, at most 60; anything that is not a positive number means no delay."""
    try:
        return min(60.0, max(0.0, float(raw.strip())))
    except ValueError:
        return 0.0


def default_projects_dir() -> Path:
    """Where a project's folder goes when the developer names none: ~/WingsProjects."""
    return Path.home() / "WingsProjects"


@dataclass(frozen=True)
class Settings:
    workspace_dir: Path = REPO_ROOT / "workspaces"
    llm_provider: str = "mock"  # mock | openai | openrouter | anthropic
    mock_script: Path = DEFAULT_MOCK_SCRIPT
    mock_delay: float = 0.0  # seconds the mock waits before each answer (WINGS_MOCK_DELAY), to see working screens
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str | None = None  # None: the SDK's default (api.anthropic.com)
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS["openrouter"]))
    efforts: dict[str, str] = field(default_factory=dict)  # tier -> Claude effort; a missing tier uses the model's default
    plantuml_jar: Path | None = None
    plantuml_server_url: str | None = None
    # Parent of the default project folders (<projects_dir>/<project slug>). None: a project gets a folder
    # only when one is named. `from_env` always sets it (WINGS_PROJECTS_DIR, else ~/WingsProjects); tests
    # that build Settings by hand leave it None and so never write into the real home folder.
    projects_dir: Path | None = None

    @staticmethod
    def default_models(provider: str) -> dict[str, str]:
        return dict(DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openrouter"]))

    @property
    def api_key(self) -> str:
        """The key of the active provider ('' for the mock)."""
        return self.key_of(self.llm_provider)

    def key_of(self, provider: str) -> str:
        return {"openai": self.openai_api_key, "openrouter": self.openrouter_api_key, "anthropic": self.anthropic_api_key}.get(provider, "")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, env_file: Path | None = ENV_FILE) -> "Settings":
        e = {**(read_env_file(env_file) if env_file else {}), **(os.environ if env is None else env)}
        base = cls()
        provider = e.get("WINGS_LLM_PROVIDER", base.llm_provider).strip().lower() or "mock"
        defaults = cls.default_models(provider)
        return cls(
            workspace_dir=Path(e.get("WINGS_WORKSPACE_DIR") or base.workspace_dir),
            llm_provider=provider,
            mock_script=Path(e.get("WINGS_MOCK_SCRIPT") or base.mock_script),
            mock_delay=_seconds(e.get("WINGS_MOCK_DELAY", "")),
            openai_api_key=e.get("OPENAI_API_KEY", "").strip(),
            openrouter_api_key=e.get("OPENROUTER_API_KEY", "").strip(),
            anthropic_api_key=e.get("ANTHROPIC_API_KEY", "").strip(),
            anthropic_base_url=e.get("ANTHROPIC_BASE_URL", "").strip() or None,
            models={tier: e.get(f"WINGS_MODEL_{tier.upper()}") or model for tier, model in defaults.items()},
            efforts={t: v for t in TIERS if (v := e.get(f"WINGS_EFFORT_{t.upper()}", "").strip().lower()) in EFFORTS},
            plantuml_jar=_jar(e.get("PLANTUML_JAR")),
            plantuml_server_url=e.get("PLANTUML_SERVER_URL") or None,
            projects_dir=Path(e["WINGS_PROJECTS_DIR"].strip()).expanduser() if e.get("WINGS_PROJECTS_DIR", "").strip() else default_projects_dir(),
        )
