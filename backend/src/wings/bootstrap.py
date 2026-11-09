"""Composition root: the only place that knows every wing and every adapter.

To add a wing: create `wings/phases/<name>/` exposing MODULE, then add it to
PHASES below in pipeline order. Nothing else needs to change.
"""

import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import httpx

from wings.adapters.documents import DocumentTextExtractor
from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.llm_openai import OpenAILLM
from wings.adapters.llm_openrouter import OpenRouterLLM
from wings.adapters.llm_unconfigured import NotConfiguredLLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.adapters.sandbox import LocalSandbox
from wings.application.orchestrator import Orchestrator
from wings.application.phase import PhaseModule
from wings.application.ports import ChatTurn, LLMClient, LLMError, LLMRequest
from wings.application.registry import PhaseRegistry
from wings.config import ENV_FILE, KEY_VARIABLE, PROVIDERS, PUBLIC_PLANTUML_SERVER, TOOLS_DIR, Settings, write_env_file
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

__all__ = ["Container", "DiagramSettings", "LLMSettings", "NotConfiguredLLM", "build_container", "build_llm", "build_registry"]


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
            "renderer_mode": self.orchestrator.renderer.mode,
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
        sandbox=LocalSandbox(),
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


PLANTUML_DOWNLOAD = "https://github.com/plantuml/plantuml/releases/download/v1.2025.4/plantuml-1.2025.4.jar"


class DiagramSettings:
    """How diagrams become pictures: the public PlantUML server (one click, sends the diagram text to
    plantuml.com) or a plantuml.jar downloaded into tools/ (private, needs Java)."""

    def __init__(self, container: Container, env_file: Path = ENV_FILE, tools_dir: Path = TOOLS_DIR, client: httpx.Client | None = None):
        self._c = container
        self._env = env_file
        self._tools = tools_dir
        self._client = client

    def _renderer(self) -> PlantUMLRenderer:
        return self._c.orchestrator.renderer  # type: ignore[return-value]

    def view(self) -> dict[str, Any]:
        s, r = self._c.settings, self._renderer()
        return {
            "mode": r.mode,
            "java": r.java,
            "jar_path": str(s.plantuml_jar) if s.plantuml_jar else None,
            "server_url": s.plantuml_server_url,
            "public_server": PUBLIC_PLANTUML_SERVER,
        }

    def _apply(self, **changes: Any) -> dict[str, Any]:
        self._c.settings = replace(self._c.settings, **changes)
        s = self._c.settings
        self._c.orchestrator.renderer = PlantUMLRenderer(s.plantuml_jar, s.plantuml_server_url)
        return self.view()

    def use_public_server(self, enabled: bool) -> dict[str, Any]:
        url = PUBLIC_PLANTUML_SERVER if enabled else None
        write_env_file(self._env, {"PLANTUML_SERVER_URL": url})
        return self._apply(plantuml_server_url=url)

    def download_jar(self) -> dict[str, Any]:
        self._tools.mkdir(parents=True, exist_ok=True)
        target = self._tools / "plantuml.jar"
        part = target.with_suffix(".part")
        client = self._client or httpx.Client(timeout=120.0, follow_redirects=True)
        try:
            with client.stream("GET", PLANTUML_DOWNLOAD) as resp:
                if resp.status_code != 200:
                    raise InvalidInputError(f"Download failed: GitHub answered {resp.status_code}.")
                with part.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
        except httpx.HTTPError as err:
            part.unlink(missing_ok=True)
            raise InvalidInputError(f"Download failed: {err}") from err
        except InvalidInputError:
            part.unlink(missing_ok=True)
            raise
        if part.stat().st_size < 1_000_000:
            part.unlink(missing_ok=True)
            raise InvalidInputError("Download failed: the file is too small to be plantuml.jar.")
        os.replace(part, target)
        write_env_file(self._env, {"PLANTUML_JAR": str(target)})
        return self._apply(plantuml_jar=target)
