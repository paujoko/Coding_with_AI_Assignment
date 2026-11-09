"""Composition root: the only place that knows every wing and every adapter.

To add a wing: create `wings/phases/<name>/` exposing MODULE, then add it to
PHASES below in pipeline order. Nothing else needs to change.
"""

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from wings.adapters.documents import DocumentTextExtractor
from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.llm_openai import OpenAILLM
from wings.adapters.llm_openrouter import OpenRouterLLM
from wings.adapters.llm_unconfigured import NotConfiguredLLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.application.orchestrator import Orchestrator
from wings.application.phase import PhaseModule
from wings.application.ports import ChatTurn, LLMClient, LLMError, LLMRequest
from wings.application.registry import PhaseRegistry
from wings.config import ENV_FILE, KEY_VARIABLE, PROVIDERS, Settings, write_env_file
from wings.domain.errors import InvalidInputError
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

PROVIDER_NAMES = {"mock": "Scripted mock", "openai": "OpenAI", "openrouter": "OpenRouter"}

__all__ = ["Container", "LLMSettings", "NotConfiguredLLM", "build_container", "build_llm", "build_registry"]


@dataclass
class Container:
    settings: Settings  # replaced when the developer changes the model provider in Settings
    orchestrator: Orchestrator

    def info(self) -> dict[str, Any]:
        s = self.settings
        return {
            "llm_provider": s.llm_provider,
            "llm_ready": not isinstance(self.orchestrator.llm, NotConfiguredLLM),
            "models": s.models if s.llm_provider != "mock" else {"all": "scripted mock"},
            "renderer": self.orchestrator.renderer.available,
            "workspace_dir": str(s.workspace_dir),
        }


def build_registry() -> PhaseRegistry:
    return PhaseRegistry(PHASES)


def build_llm(settings: Settings) -> LLMClient:
    """The model client for the configured provider. A provider without key does not stop the app:
    its stand-in explains, on the first call, how to add the key."""
    provider = settings.llm_provider
    if provider == "mock":
        return ScriptedLLM.from_file(settings.mock_script)
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown WINGS_LLM_PROVIDER '{provider}' (use {', '.join(PROVIDERS)}).")
    if not settings.api_key:
        return NotConfiguredLLM(PROVIDER_NAMES[provider], KEY_VARIABLE[provider])
    if provider == "openai":
        return OpenAILLM(settings.api_key, settings.models)
    return OpenRouterLLM(settings.api_key, settings.models)


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings.from_env()
    orchestrator = Orchestrator(
        registry=build_registry(),
        store=FileSystemStore(settings.workspace_dir),
        llm=build_llm(settings),
        renderer=PlantUMLRenderer(settings.plantuml_jar, settings.plantuml_server_url),
        extractor=DocumentTextExtractor(),
    )
    return Container(settings=settings, orchestrator=orchestrator)


def _hint(key: str) -> str:
    return f"{key[:3]}…{key[-4:]}" if len(key) >= 8 else "set"


class LLMSettings:
    """The model provider as the UI sees it: read, change (written to .env, swapped at once), test."""

    def __init__(self, container: Container, env_file: Path = ENV_FILE):
        self._c = container
        self._env = env_file

    def view(self) -> dict[str, Any]:
        s = self._c.settings
        keys = {p: k for p, k in (("openai", s.openai_api_key), ("openrouter", s.openrouter_api_key))}
        return {
            "provider": s.llm_provider,
            "providers": list(PROVIDERS),
            "ready": self._c.info()["llm_ready"],
            "key_set": bool(s.api_key),
            "key_hint": _hint(s.api_key) if s.api_key else None,
            "keys": {p: {"set": bool(k), "hint": _hint(k) if k else None} for p, k in keys.items()},
            "models": dict(s.models),
            "defaults": {p: Settings.default_models(p) for p in ("openai", "openrouter")},
            "env_file": str(self._env),
        }

    def update(self, provider: str, api_key: str | None, models: dict[str, str] | None) -> dict[str, Any]:
        provider = provider.strip().lower()
        if provider not in PROVIDERS:
            raise InvalidInputError(f"Unknown provider '{provider}'. Choose one of: {', '.join(PROVIDERS)}.")
        s = self._c.settings
        changes: dict[str, Any] = {"llm_provider": provider}
        env: dict[str, str | None] = {"WINGS_LLM_PROVIDER": provider}
        key = (api_key or "").strip()
        if key and provider in KEY_VARIABLE:
            changes["openai_api_key" if provider == "openai" else "openrouter_api_key"] = key
            env[KEY_VARIABLE[provider]] = key
        if provider != "mock":
            chosen = {t: (models or {}).get(t, "").strip() for t in ("small", "mid", "frontier")}
            current = s.models if provider == s.llm_provider else Settings.default_models(provider)
            changes["models"] = {t: chosen[t] or current[t] for t in chosen}
            env.update({f"WINGS_MODEL_{t.upper()}": m for t, m in changes["models"].items()})
        write_env_file(self._env, env)
        self._c.settings = replace(s, **changes)
        self._c.orchestrator.llm = build_llm(self._c.settings)
        return self.view()

    def test(self) -> dict[str, Any]:
        """One tiny request through the active provider (costs a fraction of a cent on a paid model)."""
        s = self._c.settings
        if s.llm_provider == "mock":
            return {"ok": True, "message": "The scripted mock model needs no connection."}
        request = LLMRequest(
            agent="connection-test",
            system="You are a connection test. Reply with the single word OK.",
            messages=[ChatTurn(role="user", content="Ping")],
            tier="small",
            json_mode=False,
        )
        started = time.perf_counter()
        try:
            reply = self._c.orchestrator.llm.complete(request)
        except LLMError as err:
            return {"ok": False, "error": str(err)}
        seconds = time.perf_counter() - started
        return {"ok": True, "message": f"Connected: {reply.model} answered in {seconds:.1f} s.", "reply": reply.text[:200]}
