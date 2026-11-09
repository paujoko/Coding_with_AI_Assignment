"""LLM agent: a named role with its own system prompt and model tier.

A phase module owns one or more agents. Agents never talk to each other
directly; they read and write artifacts through the phase context, and the
orchestrator decides who runs (manager pattern).
"""

import time
from dataclasses import dataclass

from pydantic import BaseModel

from wings.application.phase import PhaseContext
from wings.application.ports import ChatTurn, LLMReply, LLMRequest, Tier
from wings.application.structured import call_structured
from wings.domain.activity import Message, Role


def turns_from(messages: list[Message]) -> list[ChatTurn]:
    """The phase conversation as LLM chat turns (developer = user, agent = assistant)."""
    roles = {Role.DEVELOPER: "user", Role.AGENT: "assistant"}
    return [ChatTurn(role=roles[m.role], content=m.text) for m in messages if m.role in roles]


@dataclass(frozen=True)
class LLMAgent:
    name: str
    role: str  # one line, shown in the UI and the architecture docs
    system_prompt: str
    tier: Tier = "mid"

    def ask[T: BaseModel](self, ctx: PhaseContext, turns: list[ChatTurn], schema: type[T]) -> T:
        started = time.perf_counter()
        request = LLMRequest(agent=self.name, system=self.system_prompt, messages=turns, tier=self.tier)
        parsed, replies = call_structured(ctx.llm, request, schema)
        self._log(ctx, replies, started)
        return parsed

    def chat(self, ctx: PhaseContext, turns: list[ChatTurn]) -> str:
        started = time.perf_counter()
        request = LLMRequest(agent=self.name, system=self.system_prompt, messages=turns, tier=self.tier, json_mode=False)
        reply = ctx.llm.complete(request)
        self._log(ctx, [reply], started)
        return reply.text.strip()

    def _log(self, ctx: PhaseContext, replies: list[LLMReply], started: float) -> None:
        last = replies[-1]
        ctx.log(
            "agent.llm_call",
            f"{self.name} answered via {last.model} ({len(replies)} attempt{'s' if len(replies) > 1 else ''})",
            {
                "agent": self.name,
                "model": last.model,
                "attempts": len(replies),
                "seconds": round(time.perf_counter() - started, 2),
                "usage": last.usage,
                "cost_usd": sum(r.cost_usd or 0 for r in replies),
            },
        )
