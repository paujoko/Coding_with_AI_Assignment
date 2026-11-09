"""Settings from environment variables (see .env.example at the repository root)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MOCK_SCRIPT = Path(__file__).resolve().parent / "adapters" / "mock_scripts" / "demo_todo.json"


@dataclass(frozen=True)
class Settings:
    workspace_dir: Path = REPO_ROOT / "workspaces"
    llm_provider: str = "mock"  # mock | openrouter
    mock_script: Path = DEFAULT_MOCK_SCRIPT
    openrouter_api_key: str = ""
    models: dict[str, str] = field(
        default_factory=lambda: {
            "small": "google/gemma-4-26b-a4b:free",
            "mid": "z-ai/glm-5.2:free",
            "frontier": "nvidia/nemotron-3-ultra-550b:free",
        }
    )
    plantuml_jar: Path | None = None
    plantuml_server_url: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        base = cls()
        return cls(
            workspace_dir=Path(e.get("WINGS_WORKSPACE_DIR", base.workspace_dir)),
            llm_provider=e.get("WINGS_LLM_PROVIDER", base.llm_provider).lower(),
            mock_script=Path(e.get("WINGS_MOCK_SCRIPT", base.mock_script)),
            openrouter_api_key=e.get("OPENROUTER_API_KEY", ""),
            models={tier: e.get(f"WINGS_MODEL_{tier.upper()}", model) for tier, model in base.models.items()},
            plantuml_jar=Path(e["PLANTUML_JAR"]) if e.get("PLANTUML_JAR") else None,
            plantuml_server_url=e.get("PLANTUML_SERVER_URL") or None,
        )
