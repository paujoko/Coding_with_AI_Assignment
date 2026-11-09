import json

import pytest

from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.application.orchestrator import Orchestrator
from wings.bootstrap import build_registry
from wings.config import DEFAULT_MOCK_SCRIPT


def as_text(reply) -> str:
    return reply if isinstance(reply, str) else json.dumps(reply)


@pytest.fixture
def demo_script() -> dict:
    return json.loads(DEFAULT_MOCK_SCRIPT.read_text(encoding="utf-8"))


@pytest.fixture
def make_orchestrator(tmp_path):
    """Full registry, real file store in tmp_path, scripted LLM from a dict of agent -> replies."""

    def build(script: dict) -> Orchestrator:
        llm = ScriptedLLM({agent: [as_text(r) for r in replies] for agent, replies in script.items()})
        return Orchestrator(build_registry(), FileSystemStore(tmp_path / "ws"), llm, PlantUMLRenderer())

    return build
