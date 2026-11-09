"""Scripted LLM: replays canned replies per agent. The default provider.

Used by every test and by the demo mode, so the whole pipeline runs without an
API key and without cost. Script keys are agent names; plain chat calls
(json_mode=False) look up "<agent>:chat" first.

The reply is chosen by the conversation stage, not by a call counter: reply N
answers a request that already contains N assistant turns (the last reply
repeats). That keeps the mock deterministic across processes, so the CLI and
the server behave the same, and a retry naturally moves to the next reply.

Tool use: when a request offers tools and the script has "<agent>:tools", the
mock first plays those entries as tool-call rounds ({"tool_calls": [{"name",
"arguments"}]}), one per round, then answers as above. Tool rounds do not count
as stages.
"""

import json
from pathlib import Path

from wings.application.ports import LLMError, LLMReply, LLMRequest, ToolCall


class ScriptedLLM:
    def __init__(self, script: dict[str, list[str]]):
        self._script = {k: list(v) for k, v in script.items()}
        self.calls: list[LLMRequest] = []

    @classmethod
    def from_file(cls, path: Path) -> "ScriptedLLM":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        # Values may be JSON objects for readability; the LLM contract is text.
        return cls({k: [v if isinstance(v, str) else json.dumps(v) for v in replies] for k, replies in raw.items()})

    def complete(self, request: LLMRequest) -> LLMReply:
        self.calls.append(request)
        tool_rounds = self._script.get(f"{request.agent}:tools", [])
        done = sum(1 for t in request.messages if t.role == "assistant" and t.tool_calls)
        if request.tools and done < len(tool_rounds):
            planned = json.loads(tool_rounds[done]).get("tool_calls", [])
            calls = [ToolCall(id=f"mock-{done}-{i}", name=c["name"], arguments=c.get("arguments", {})) for i, c in enumerate(planned)]
            return LLMReply(text="", model=f"mock/{request.agent}", tool_calls=calls, cost_usd=0.0)
        key = f"{request.agent}:chat" if not request.json_mode and f"{request.agent}:chat" in self._script else request.agent
        replies = self._script.get(key)
        if not replies:
            raise LLMError(f"Mock script has no reply for agent '{key}'.")
        stage = sum(1 for turn in request.messages if turn.role == "assistant" and not turn.tool_calls)
        index = min(stage, len(replies) - 1)
        return LLMReply(text=replies[index], model=f"mock/{key}", usage={"prompt_tokens": 0, "completion_tokens": 0}, cost_usd=0.0)
