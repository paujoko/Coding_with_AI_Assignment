"""Claude through Anthropic's Messages API, with the official `anthropic` SDK and the developer's own key.

The tier of the calling agent picks the model. Only humans run this against the real API; tests
inject a fake transport (`http_client=httpx2.Client(transport=httpx2.MockTransport(...))`).

What differs from the OpenAI-compatible adapters (ADR 0021):
- No JSON mode: the Messages API has none. The schema in the prompt, validation and the retry in
  `call_structured` enforce the JSON, as they do for every provider.
- Every answer is streamed, so a long answer (P4 Code took 318 s on Opus) never hits an HTTP timeout.
- Thinking is left to the model's default: adaptive on the current Claude models. The developer can
  set an effort per tier in Settings (`output_config.effort`).
- Claude's own content blocks (thinking blocks above all) go back unchanged with the tool calls they
  belong to (`LLMReply.provider_content` -> `ChatTurn.provider_content`).
- Where the model supports it, the server-side refusal fallback is on: if a safety classifier
  declines, the API reruns the request on a fallback model inside the same call.
- Anthropic reports no cost; it is computed from the tokens and `pricing.py`.
"""

import json
import logging
from typing import Any

import anthropic
import httpx2

from wings.adapters.pricing import cost_usd
from wings.application.ports import ChatTurn, LLMError, LLMReply, LLMRequest, Tier, ToolCall

_log = logging.getLogger("wings.llm")

EFFORTS = ("low", "medium", "high", "xhigh", "max")
MAX_TOKENS = 64_000  # streamed, so a high cap costs nothing unless used; long code files need room
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that accept `fallbacks: "default"` (Anthropic's model docs, 2026-11-03). Haiku has no
# server-side fallback; on it a refusal is reported as an error.
FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1", "claude-opus-5")

_HINTS = {
    400: "the request was refused; the reason follows",
    401: "the API key is wrong or revoked; paste a new one in Settings",
    402: "no credit left on the account; add credit in the Claude Console",
    403: "the key has no access to this model or workspace",
    404: "the model name does not exist for this key; check the models in Settings",
    413: "the request is too large",
    429: "rate limit or spend limit reached; wait a minute or raise the limit in the Claude Console",
    500: "an error on Anthropic's side; try again",
    529: "Anthropic's servers are overloaded right now; try again in a minute",
}
_DROP_BEFORE_FALLBACK = {"thinking", "redacted_thinking", "tool_use", "server_tool_use"}


def _text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": text}] if text.strip() else []


def _assistant_blocks(turn: ChatTurn) -> list[dict[str, Any]]:
    """Claude's own blocks when they hold an answer or a tool call, else blocks built from the turn."""
    blocks = turn.provider_content or []
    if any(b.get("type") == "tool_use" or (b.get("type") == "text" and str(b.get("text", "")).strip()) for b in blocks):
        return [dict(b) for b in blocks]
    built = _text(turn.content) + [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in turn.tool_calls]
    return built or [{"type": "text", "text": "(no answer)"}]  # the API refuses an empty assistant turn


def to_messages(turns: list[ChatTurn]) -> list[dict[str, Any]]:
    """Wings chat turns as Messages API messages. Tool results become tool_result blocks in a user
    message; consecutive turns of one role are merged, so all results of one round share a message."""
    out: list[dict[str, Any]] = []
    for turn in turns:
        if turn.role == "tool":
            role, blocks = "user", [{"type": "tool_result", "tool_use_id": turn.tool_call_id or "", "content": turn.content or "(no output)"}]
        elif turn.role == "assistant":
            role, blocks = "assistant", _assistant_blocks(turn)
        else:
            role, blocks = "user", _text(turn.content) or [{"type": "text", "text": "(empty message)"}]
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": list(blocks)})
    if not out or out[0]["role"] != "user":  # the first message must be the user's
        out.insert(0, {"role": "user", "content": [{"type": "text", "text": "(The conversation so far follows.)"}]})
    if out[-1]["role"] != "user":  # current models refuse a request that ends on an assistant turn (prefill)
        out.append({"role": "user", "content": [{"type": "text", "text": "Continue."}]})
    return out


def _after_last_fallback(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """After a mid-answer fallback, the declined model's thinking and tool calls are neither run nor
    sent back; its text stays (the fallback model continued from it). Refusal fallback rules."""
    last = max((i for i, b in enumerate(blocks) if b.get("type") == "fallback"), default=-1)
    return [b for i, b in enumerate(blocks) if i >= last or b.get("type") not in _DROP_BEFORE_FALLBACK]


class AnthropicLLM:
    provider = "Anthropic"
    key_name = "ANTHROPIC_API_KEY"

    def __init__(
        self,
        api_key: str,
        models: dict[Tier, str],
        efforts: dict[str, str] | None = None,
        base_url: str | None = None,
        http_client: httpx2.Client | None = None,
        max_retries: int = 2,
        max_tokens: int = MAX_TOKENS,
    ):
        if not api_key:
            raise ValueError(f"{self.key_name} is empty.")
        self._key_prefix = api_key[:6]
        self._models = models
        self._efforts = {t: e for t, e in (efforts or {}).items() if e in EFFORTS}
        self._max_tokens = max_tokens
        # The SDK retries 408, 409, 429, 5xx and 529 itself (max_retries) before an error reaches us.
        self._client = anthropic.Anthropic(api_key=api_key, base_url=base_url, http_client=http_client, max_retries=max_retries)

    def complete(self, request: LLMRequest) -> LLMReply:
        model = self._models[request.tier]
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": self._max_tokens,
            "system": request.system,
            "messages": to_messages(request.messages),
        }
        if request.tools:
            params["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in request.tools]
            if request.tool_choice == "none":
                params["tool_choice"] = {"type": "none"}
        if effort := self._efforts.get(request.tier):
            params["output_config"] = {"effort": effort}
        if model in FALLBACK_MODELS:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        _log.debug("REQUEST agent=%s model=%s\n%s", request.agent, model, json.dumps(params, indent=2, ensure_ascii=False))
        try:
            with self._client.beta.messages.stream(**params) as stream:
                message = stream.get_final_message()
        except anthropic.APIStatusError as err:
            raise LLMError(self._explain(err)) from err
        except anthropic.APIConnectionError as err:  # includes timeouts
            raise LLMError(f"Anthropic request failed: {err}") from err
        except anthropic.APIError as err:  # an error event in the middle of the stream
            raise LLMError(f"Anthropic stopped the answer: {err}") from err

        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) or "no category given"
            raise LLMError(
                f"Claude declined this request ({category}). Rephrase the input, or choose another model for this tier in Settings."
            )
        blocks = _after_last_fallback([b.to_dict(mode="json", exclude_none=True) for b in message.content])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = [
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input") if isinstance(b.get("input"), dict) else {})
            for b in blocks
            if b.get("type") == "tool_use"
        ]
        if message.stop_reason == "max_tokens":
            calls = []  # a tool call cut off by the token limit is incomplete; never run it
        usage = message.usage
        read = usage.cache_read_input_tokens or 0
        write = usage.cache_creation_input_tokens or 0
        counts = {"prompt_tokens": usage.input_tokens + read + write, "completion_tokens": usage.output_tokens}
        if read:
            counts["cache_read_input_tokens"] = read
        if write:
            counts["cache_creation_input_tokens"] = write
        _log.debug(
            "RESPONSE agent=%s model=%s stop=%s\nTOOL_CALLS=%s\n%s",
            request.agent,
            message.model,
            message.stop_reason,
            [{"name": c.name, "args": c.arguments} for c in calls],
            text,
        )
        return LLMReply(
            text=text,
            model=message.model,
            usage=counts,
            cost_usd=cost_usd(message.model, usage.input_tokens, usage.output_tokens, read, write),
            tool_calls=calls,
            provider_content=blocks,
        )

    def _explain(self, err: anthropic.APIStatusError) -> str:
        status = err.status_code
        hint = _HINTS.get(status) or ("an error on Anthropic's side; try again" if status >= 500 else None)
        if status == 401 and self._key_prefix.startswith("sk-or-"):
            hint = "this is an OpenRouter key (it starts with sk-or-); choose OpenRouter in Settings"
        body = err.body if isinstance(err.body, dict) else {}
        detail = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else None
        request_id = getattr(err, "request_id", None)
        where = f" [request {request_id}]" if request_id else ""
        return f"Anthropic returned {status}{f' ({hint})' if hint else ''}: {(detail or err.message)[:300]}{where}"
