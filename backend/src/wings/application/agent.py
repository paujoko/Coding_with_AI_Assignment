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
from wings.domain.phases import PhaseId


def turns_from(messages: list[Message]) -> list[ChatTurn]:
    """The phase conversation as LLM chat turns (developer = user, agent = assistant)."""
    roles = {Role.DEVELOPER: "user", Role.AGENT: "assistant"}
    return [ChatTurn(role=roles[m.role], content=m.text) for m in messages if m.role in roles]


DOC_CHARS = 20_000  # per document
DOCS_CHARS = 60_000  # all documents of one request


def document_turns(ctx: PhaseContext, *phases: PhaseId) -> list[ChatTurn]:
    """Attached documents of the given phases (default: this one) as one user turn, empty when there are none.
    Long texts are cut so a large document cannot crowd out the conversation."""
    docs = list({d.id: d for ph in (phases or (ctx.phase,)) for d in ctx.documents(ph)}.values())
    if not docs:
        return []
    parts, budget = [], DOCS_CHARS
    for d in docs:
        text = d.text[: min(DOC_CHARS, budget)]
        budget -= len(text)
        cut = " (shortened)" if len(text) < len(d.text) else ""
        parts.append(f"### {d.name}{cut}\n{text}")
        if budget <= 0:
            break
    return [ChatTurn(role="user", content="Documents the developer attached:\n\n" + "\n\n".join(parts))]


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
        seconds = time.perf_counter() - started
        attempts = f"{len(replies)} attempts" if len(replies) > 1 else "1 attempt"
        ctx.log(
            "agent.llm_call",
            f"{self.name.capitalize()} replied ({last.model}, {attempts}, {seconds:.1f} s)",
            {
                "agent": self.name,
                "model": last.model,
                "attempts": len(replies),
                "seconds": round(seconds, 2),
                "usage": last.usage,
                "cost_usd": sum(r.cost_usd or 0 for r in replies),
            },
        )
