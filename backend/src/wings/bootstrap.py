"""Composition root: the only place that knows every wing and every adapter.

To add a wing: create `wings/phases/<name>/` exposing MODULE, then add it to
PHASES below in pipeline order. Nothing else needs to change.
"""

from dataclasses import dataclass

from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.llm_openrouter import OpenRouterLLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.application.orchestrator import Orchestrator
from wings.application.phase import PhaseModule
from wings.application.ports import LLMClient
from wings.application.registry import PhaseRegistry
from wings.config import Settings
from wings.phases import codegen, deployment, design, maintenance, refinement, requirements, testing

PHASES: list[PhaseModule] = [
    requirements.MODULE,
    design.MODULE,
    refinement.MODULE,
    codegen.MODULE,
    testing.MODULE,
    deployment.MODULE,
    maintenance.MODULE,
]


@dataclass(frozen=True)
class Container:
    settings: Settings
    orchestrator: Orchestrator

    def info(self) -> dict:
        s = self.settings
        return {
            "llm_provider": s.llm_provider,
            "models": s.models if s.llm_provider != "mock" else {"all": "scripted mock"},
            "renderer": self.orchestrator.renderer.available,
            "workspace_dir": str(s.workspace_dir),
        }


def build_registry() -> PhaseRegistry:
    return PhaseRegistry(PHASES)


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "mock":
        return ScriptedLLM.from_file(settings.mock_script)
    if settings.llm_provider == "openrouter":
        return OpenRouterLLM(settings.openrouter_api_key, settings.models)
    raise ValueError(f"Unknown WINGS_LLM_PROVIDER '{settings.llm_provider}' (use mock or openrouter).")


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings.from_env()
    orchestrator = Orchestrator(
        registry=build_registry(),
        store=FileSystemStore(settings.workspace_dir),
        llm=build_llm(settings),
        renderer=PlantUMLRenderer(settings.plantuml_jar, settings.plantuml_server_url),
    )
    return Container(settings=settings, orchestrator=orchestrator)
