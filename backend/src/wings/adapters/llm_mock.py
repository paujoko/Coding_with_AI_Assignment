"""Scripted LLM: replays canned replies per agent. The default provider.

Used by every test and by the demo mode, so the whole pipeline runs without an
API key and without cost. Script keys are agent names; plain chat calls
(json_mode=False) look up "<agent>:chat" first.

The reply is chosen by the conversation stage, not by a call counter: reply N
answers a request that already contains N assistant turns (the last reply
repeats). That keeps the mock deterministic across processes, so the CLI and
the server behave the same, and a retry naturally moves to the next reply.
"""

import json
from pathlib import Path

from wings.application.ports import LLMError, LLMReply, LLMRequest


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
        key = f"{request.agent}:chat" if not request.json_mode and f"{request.agent}:chat" in self._script else request.agent
        replies = self._script.get(key)
        if not replies:
            raise LLMError(f"Mock script has no reply for agent '{key}'.")
        stage = sum(1 for turn in request.messages if turn.role == "assistant")
        index = min(stage, len(replies) - 1)
        return LLMReply(text=replies[index], model=f"mock/{key}", usage={"prompt_tokens": 0, "completion_tokens": 0}, cost_usd=0.0)
