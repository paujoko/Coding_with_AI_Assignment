import json

import pytest

from wings.adapters.documents import DocumentTextExtractor
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
        return Orchestrator(build_registry(), FileSystemStore(tmp_path / "ws"), llm, PlantUMLRenderer(), extractor=DocumentTextExtractor())

    return build


def walk_to(orch, phase, name: str = "Todo") -> str:
    """A project with every phase before `phase` done and approved on the demo script (the happy path)."""
    from wings.domain.phases import PhaseId as P

    steps = {
        P.REQUIREMENTS: [("start", {"description": "A todo app"}), ("answer", {"answers": "CLI"})],
        P.DESIGN: [("generate", {})],
        P.REFINEMENT: [("review", {}), ("apply", {"findings": ["F1", "F2"]})],
        P.CODEGEN: [("generate", {})],
        P.TESTING: [("generate", {}), ("run", {})],
        P.DEPLOYMENT: [("generate", {})],
    }
    pid = orch.create_project(name).id
    for ph in P:
        if ph == phase:
            break
        for action, payload in steps[ph]:
            orch.run_action(pid, ph, action, payload)
        orch.approve(pid, ph)
    return pid


@pytest.fixture
def walk():
    return walk_to
