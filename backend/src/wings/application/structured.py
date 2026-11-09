"""Structured LLM output: ask for JSON matching a Pydantic schema, validate, retry once.

Every agent goes through here, so every provider gets the same parsing and the
same failure behaviour (LLMOutputError after the retries are used up).
"""

import json
import re
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from wings.application.ports import ChatTurn, LLMClient, LLMReply, LLMRequest, ToolCall

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class LLMOutputError(Exception):
    def __init__(self, message: str, raw: str):
        super().__init__(message)
        self.raw = raw


def schema_instructions(schema: type[BaseModel]) -> str:
    return (
        "Reply with a single JSON object and nothing else. It must validate against this JSON schema:\n"
        + json.dumps(schema.model_json_schema(), indent=1)
    )


def extract_json(text: str) -> str:
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text.strip()


def call_structured[T: BaseModel](
    llm: LLMClient,
    request: LLMRequest,
    schema: type[T],
    retries: int = 1,
    run_tool: Callable[[ToolCall], str] | None = None,
    max_tool_rounds: int = 4,
) -> tuple[T, list[LLMReply]]:
    """Returns the parsed object and every raw reply (for logging and cost tracking).

    With tools offered (`request.tools` and `run_tool`), the model may first call tools; their
    results go back as tool turns until it answers. After `max_tool_rounds` the tools are
    withdrawn and the model is told to answer.
    """
    req = request.model_copy(update={"system": f"{request.system}\n\n{schema_instructions(schema)}", "json_mode": True})
    replies: list[LLMReply] = []
    rounds = 0
    for attempt in range(retries + 1):
        reply = llm.complete(req)
        replies.append(reply)
        while reply.tool_calls and run_tool is not None and req.tools and rounds < max_tool_rounds:
            results = [ChatTurn(role="tool", tool_call_id=c.id, content=run_tool(c)) for c in reply.tool_calls]
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
                raise LLMOutputError(f"{request.agent} returned invalid output after {retries + 1} attempts: {err}", reply.text) from err
            req = req.model_copy(
                update={
                    "messages": [
                        *req.messages,
                        ChatTurn(role="assistant", content=reply.text),
                        ChatTurn(role="user", content=f"That reply was not valid: {err}. Reply again with corrected JSON only."),
                    ]
                }
            )
    raise AssertionError("unreachable")
