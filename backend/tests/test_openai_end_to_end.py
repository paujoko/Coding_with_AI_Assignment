"""Is everything ready for a real model? The real OpenAI adapter, a fake OpenAI server, the whole P1 -> P2 path.

The fake server answers like the OpenAI chat completions API: it reads the system prompt to know
which agent is asking, returns JSON in `content`, and once asks for tools like a real model would.
No network, no cost.
"""

import copy
import json

import httpx

from wings.adapters.documents import DocumentTextExtractor
from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_openai import OpenAILLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.application.orchestrator import Orchestrator
from wings.bootstrap import build_registry
from wings.domain.phases import PhaseId as P


def fake_openai(script: dict) -> tuple[httpx.Client, list[dict]]:
    seen: list[dict] = []
    analyst_final = copy.deepcopy(script["analyst"][1])
    architect = script["architect"][0]

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append(body)
        system = body["messages"][0]["content"]
        assert req.headers["authorization"] == "Bearer sk-test"
        if "architect" in system.lower():
            if body.get("tools") and not any(m["role"] == "tool" for m in body["messages"]):
                calls = [{"id": "call_1", "type": "function", "function": {"name": "check_coverage", "arguments": json.dumps({"covers": ["REQ-001"]})}}]
                message = {"role": "assistant", "content": None, "tool_calls": calls}
            else:
                message = {"role": "assistant", "content": json.dumps(architect)}
        else:
            message = {"role": "assistant", "content": json.dumps(analyst_final)}
        return httpx.Response(200, json={"model": body["model"], "choices": [{"message": message}], "usage": {"total_tokens": 42}})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_openai_adapter_drives_requirements_and_design(tmp_path, demo_script):
    client, seen = fake_openai(demo_script)
    llm = OpenAILLM("sk-test", {"small": "gpt-s", "mid": "gpt-m", "frontier": "gpt-f"}, client=client)
    orch = Orchestrator(build_registry(), FileSystemStore(tmp_path / "ws"), llm, PlantUMLRenderer(), extractor=DocumentTextExtractor())
    pid = orch.create_project("Real model").id

    drafted = orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "A todo app"})
    assert drafted.project.status(P.REQUIREMENTS).value == "draft"
    assert drafted.outcome.artifacts[0].defines == ["REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005"]
    assert seen[0]["model"] == "gpt-m" and seen[0]["response_format"] == {"type": "json_object"}

    orch.approve(pid, P.REQUIREMENTS)
    design = orch.run_action(pid, P.DESIGN, "generate", {})
    assert len(design.outcome.artifacts) == 3
    architect = [b for b in seen if b["model"] == "gpt-f"]
    assert architect[0]["tools"] and architect[1]["messages"][-1]["role"] == "tool"
    assert "Not covered" in architect[1]["messages"][-1]["content"]  # the tool answered what the model asked
    assert any(e.kind == "agent.tool_call" for e in orch.store.list_events(pid))
