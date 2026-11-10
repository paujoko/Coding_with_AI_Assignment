"""Structured LLM output: ask for JSON matching a Pydantic schema, validate, retry.

Every agent goes through here, so every provider gets the same parsing and the
same failure behaviour (LLMOutputError after the retries are used up).
"""

import json
import re
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from wings.application.ports import ChatTurn, LLMClient, LLMReply, LLMRequest, ToolCall

_FENCE = re.compile(r"```(?:json)?[ \t]*\n(.*?)```", re.DOTALL)


class LLMOutputError(Exception):
    """The model's answer could not be used. `raw` is the last reply, `replies` all of them (for cost)."""

    def __init__(self, message: str, raw: str, replies: list[LLMReply] | None = None):
        super().__init__(message)
        self.raw = raw
        self.replies = replies or []


def schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "Reply with a single JSON object and nothing else. It must validate against this JSON schema:\n"
        + json.dumps(schema.model_json_schema(), indent=1)
    )


def extract_json(text: str) -> str:
    """The JSON part of a reply. A reply that is JSON as a whole is taken as it is: a code fence
    inside one of its strings (a DEPLOY.md with a ```bash block, real run s03) is not the answer."""
    stripped = text.strip()
    try:
        json.loads(stripped)
        return stripped
    except ValueError:
        pass
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else stripped


def short_reason(err: Exception, text: str) -> str:
    """One line a developer can read: what was wrong with the reply, without library noise."""
    if not text.strip():
        return "the reply was empty"
    if isinstance(err, ValidationError):
        parts = []
        for e in err.errors(include_url=False)[:3]:
            if e["type"] == "json_invalid":
                parts.append("the reply was not valid JSON")
                continue
            where = ".".join(str(x) for x in e["loc"]) or "answer"
            parts.append(f"{where}: {e['msg'].removeprefix('Value error, ')}")
        more = len(err.errors()) - 3
        return "; ".join(parts) + (f" (and {more} more)" if more > 0 else "")
    return str(err).splitlines()[0]


def _retry_message(err: Exception, text: str) -> str:
    if not text.strip():
        return "Your reply was empty. Reply with the JSON object now, nothing else."
    return f"That reply was not valid: {err}. Reply again with corrected JSON only."


def call_structured[T: BaseModel](
    llm: LLMClient,
    request: LLMRequest,
    schema: type[T],
    retries: int = 2,
    run_tool: Callable[[ToolCall], str] | None = None,
    max_tool_rounds: int = 4,
) -> tuple[T, list[LLMReply]]:
    """Returns the parsed object and every raw reply (for logging and cost tracking).

    With tools offered (`request.tools` and `run_tool`), the model may first call tools; their
    results go back as tool turns until it answers. After `max_tool_rounds` the tools are
    withdrawn and the model is told to answer. A call repeated with the same arguments is not run
    again: the model gets the earlier result and is told so (real run s03: the tester re-checked
    unchanged files every round). Two retries, because DeepSeek sometimes returned empty content.
    """
    req = request.model_copy(update={"system": f"{request.system}\n\n{schema_instructions(schema)}", "json_mode": True})
    replies: list[LLMReply] = []
    rounds = 0
    seen: dict[str, str] = {}

    def answer(call: ToolCall) -> str:
        key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
        if key in seen:
            return f"(already checked with the same input; the result was:)\n{seen[key]}\nDo not repeat this call; answer when you are done."
        seen[key] = run_tool(call)  # type: ignore[misc]
        return seen[key]

    for attempt in range(retries + 1):
        reply = llm.complete(req)
        replies.append(reply)
        while reply.tool_calls and run_tool is not None and req.tools and rounds < max_tool_rounds:
            results = [ChatTurn(role="tool", tool_call_id=c.id, content=answer(c)) for c in reply.tool_calls]
            turns = [*req.messages, ChatTurn(role="assistant", content=reply.text, tool_calls=reply.tool_calls), *results]
            rounds += 1
            if rounds == max_tool_rounds:
                turns.append(ChatTurn(role="user", content="No more tool calls. Answer now with the JSON."))
                req = req.model_copy(update={"messages": turns, "tools": []})
            else:
                req = req.model_copy(update={"messages": turns})
            reply = llm.complete(req)
            replies.append(reply)
        try:
            return schema.model_validate_json(extract_json(reply.text)), replies
        except (ValidationError, ValueError) as err:
            if attempt == retries:
                who = request.agent.replace("_", " ").capitalize()
                reason = short_reason(err, reply.text)
                raise LLMOutputError(f"{who}'s answer could not be used after {retries + 1} attempts: {reason}.", reply.text, replies) from err
            req = req.model_copy(
                update={
                    "messages": [
                        *req.messages,
                        ChatTurn(role="assistant", content=reply.text),
                        ChatTurn(role="user", content=_retry_message(err, reply.text)),
                    ]
                }
            )
    raise AssertionError("unreachable")
