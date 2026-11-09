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

PROVIDERS = ("mock", "openai", "openrouter")

# Models per agent tier. The analyst uses "mid", the architect "frontier" (see each wing).
# Check the current model names with your provider; they can be changed in Settings.
DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "openai": {"small": "gpt-5-nano", "mid": "gpt-5-mini", "frontier": "gpt-5"},
    "openrouter": {
        "small": "google/gemma-4-26b-a4b:free",
        "mid": "z-ai/glm-5.2:free",
        "frontier": "nvidia/nemotron-3-ultra-550b:free",
    },
}

KEY_VARIABLE = {"openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}


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


@dataclass(frozen=True)
class Settings:
    workspace_dir: Path = REPO_ROOT / "workspaces"
    llm_provider: str = "mock"  # mock | openai | openrouter
    mock_script: Path = DEFAULT_MOCK_SCRIPT
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS["openrouter"]))
    plantuml_jar: Path | None = None
    plantuml_server_url: str | None = None

    @staticmethod
    def default_models(provider: str) -> dict[str, str]:
        return dict(DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openrouter"]))

    @property
    def api_key(self) -> str:
        """The key of the active provider ('' for the mock)."""
        return {"openai": self.openai_api_key, "openrouter": self.openrouter_api_key}.get(self.llm_provider, "")

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
            openai_api_key=e.get("OPENAI_API_KEY", "").strip(),
            openrouter_api_key=e.get("OPENROUTER_API_KEY", "").strip(),
            models={tier: e.get(f"WINGS_MODEL_{tier.upper()}") or model for tier, model in defaults.items()},
            plantuml_jar=Path(e["PLANTUML_JAR"]) if e.get("PLANTUML_JAR") else None,
            plantuml_server_url=e.get("PLANTUML_SERVER_URL") or None,
        )
