"""The Anthropic adapter against a fake HTTP transport. No test ever reaches the real API.

The fake answers like the Messages API does when streaming: server-sent events built from the
content blocks a test gives it. The adapter talks through the official `anthropic` SDK, which
is built on httpx2, so the fake transport is an httpx2.MockTransport.
"""

import json

import httpx2
import pytest

from wings.adapters.llm_anthropic import AnthropicLLM
from wings.application.ports import ChatTurn, LLMError, LLMRequest, ToolCall, ToolSpec

MODELS = {"small": "claude-haiku-5-5", "mid": "claude-sonnet-5-5", "frontier": "claude-opus-5-5"}
SPEC = ToolSpec(name="check_plantuml", description="Check a diagram.", parameters={"type": "object", "properties": {"source": {"type": "string"}}})


def sse(blocks: list[dict], model: str = "claude-sonnet-5-5", stop: str = "end_turn", usage: dict | None = None, stop_details: dict | None = None) -> bytes:
    """A streamed Messages API answer that ends with exactly these content blocks."""
    usage = usage or {"input_tokens": 100, "output_tokens": 20}
    events: list[dict] = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {**usage, "output_tokens": 1},
            },
        }
    ]
    for i, block in enumerate(blocks):
        kind = block["type"]
        if kind == "text":
            events += [
                {"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": block["text"]}},
            ]
        elif kind == "thinking":
            events += [
                {"type": "content_block_start", "index": i, "content_block": {"type": "thinking", "thinking": "", "signature": ""}},
                {"type": "content_block_delta", "index": i, "delta": {"type": "signature_delta", "signature": block["signature"]}},
            ]
        elif kind == "tool_use":
            events += [
                {"type": "content_block_start", "index": i, "content_block": {"type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}},
                {"type": "content_block_delta", "index": i, "delta": {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}},
            ]
        else:
            events.append({"type": "content_block_start", "index": i, "content_block": block})
        events.append({"type": "content_block_stop", "index": i})
    delta: dict = {"stop_reason": stop, "stop_sequence": None}
    if stop_details:
        delta["stop_details"] = stop_details
    events += [{"type": "message_delta", "delta": delta, "usage": {"output_tokens": usage["output_tokens"]}}, {"type": "message_stop"}]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


class FakeAPI:
    """Records every request; answers with the next prepared response."""

    def __init__(self, *answers: httpx2.Response):
        self.answers = list(answers)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]

    @property
    def body(self) -> dict:
        return json.loads(self.requests[-1].content)


def streamed(blocks: list[dict], **kw) -> httpx2.Response:
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse(blocks, **kw))


def error(status: int, message: str = "x", kind: str = "error") -> httpx2.Response:
    return httpx2.Response(status, json={"type": "error", "error": {"type": kind, "message": message}})


def llm(api: FakeAPI, key: str = "sk-ant-test", **kw) -> AnthropicLLM:
    return AnthropicLLM(key, MODELS, http_client=httpx2.Client(transport=httpx2.MockTransport(api)), max_retries=0, **kw)


def ask(tier="mid", messages=None, tools=None, json_mode=True, tool_choice="auto") -> LLMRequest:
    return LLMRequest(
        agent="analyst",
        system="You write requirements.",
        messages=messages or [ChatTurn(role="user", content="A to-do app")],
        tier=tier,
        json_mode=json_mode,
        tools=tools or [],
        tool_choice=tool_choice,
    )


def test_request_maps_system_turns_and_model_and_streams():
    api = FakeAPI(streamed([{"type": "text", "text": '{"ok": true}'}]))
    reply = llm(api).complete(ask(messages=[ChatTurn(role="user", content="hi"), ChatTurn(role="assistant", content="Which users?"), ChatTurn(role="user", content="Students")]))
    req, body = api.requests[0], api.body
    assert str(req.url).startswith("https://api.anthropic.com/v1/messages")
    assert req.headers["authorization"] == "Bearer sk-ant-test"  # how SDK 2.x sends an API key
    assert body["model"] == "claude-sonnet-5-5"
    assert body["system"] == "You write requirements."
    assert body["stream"] is True  # long answers never hit an HTTP timeout
    assert body["max_tokens"] >= 32000
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert body["messages"][1]["content"] == [{"type": "text", "text": "Which users?"}]
    assert "tools" not in body
    assert (reply.text, reply.model, reply.tool_calls) == ('{"ok": true}', "claude-sonnet-5-5", [])


def test_no_json_mode_and_no_thinking_switch_is_sent():
    """The Messages API has no `response_format: json_object`; the schema in the prompt, validation and
    the retry in call_structured enforce the JSON. Thinking is left to the model's default (adaptive
    on the current Claude models), so an older model id in Settings cannot make the request invalid."""
    api = FakeAPI(streamed([{"type": "text", "text": "{}"}]))
    llm(api).complete(ask(json_mode=True))
    assert not {"response_format", "thinking", "temperature"} & set(api.body)


def test_effort_per_tier_goes_into_output_config():
    api = FakeAPI(streamed([{"type": "text", "text": "{}"}]))
    client = llm(api, efforts={"frontier": "low"})
    client.complete(ask(tier="frontier"))
    assert api.body["output_config"] == {"effort": "low"}
    client.complete(ask(tier="mid"))
    assert "output_config" not in api.body  # no effort chosen: the model's own default


def test_refusal_fallback_is_asked_for_where_the_model_supports_it():
    api = FakeAPI(streamed([{"type": "text", "text": "{}"}]))
    client = llm(api)
    client.complete(ask(tier="mid"))  # claude-sonnet-5-5
    assert api.body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in api.requests[-1].headers["anthropic-beta"]
    client.complete(ask(tier="small"))  # claude-haiku-5-5 has no server-side fallback
    assert "fallbacks" not in api.body and "anthropic-beta" not in api.requests[-1].headers


def test_tools_and_a_tool_round_trip_keep_claudes_own_blocks():
    """A tool call comes back with Claude's thinking block. The next request must send that block back
    unchanged before the tool_use, and every tool result in one user message."""
    api = FakeAPI(
        streamed(
            [
                {"type": "thinking", "signature": "sig-1"},
                {"type": "text", "text": "Let me check."},
                {"type": "tool_use", "id": "toolu_1", "name": "check_plantuml", "input": {"source": "@startuml\n@enduml"}},
                {"type": "tool_use", "id": "toolu_2", "name": "check_plantuml", "input": {"source": "x"}},
            ],
            stop="tool_use",
        ),
        streamed([{"type": "text", "text": "{}"}]),
    )
    client = llm(api)
    first = client.complete(ask(tools=[SPEC]))
    assert api.body["tools"] == [{"name": "check_plantuml", "description": "Check a diagram.", "input_schema": SPEC.parameters}]
    assert "tool_choice" not in api.body
    assert first.tool_calls == [
        ToolCall(id="toolu_1", name="check_plantuml", arguments={"source": "@startuml\n@enduml"}),
        ToolCall(id="toolu_2", name="check_plantuml", arguments={"source": "x"}),
    ]
    assert first.text == "Let me check."

    history = [
        ChatTurn(role="user", content="Draw it"),
        ChatTurn(role="assistant", content=first.text, tool_calls=first.tool_calls, provider_content=first.provider_content),
        ChatTurn(role="tool", tool_call_id="toolu_1", content="OK"),
        ChatTurn(role="tool", tool_call_id="toolu_2", content="line 1: missing @startuml"),
        ChatTurn(role="user", content="No more tool calls. Answer now with the JSON."),
    ]
    client.complete(ask(messages=history, tools=[SPEC], tool_choice="none"))
    sent = api.body["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[1]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig-1"}
    assert [b["type"] for b in sent[1]["content"]] == ["thinking", "text", "tool_use", "tool_use"]
    assert sent[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "OK"},
        {"type": "tool_result", "tool_use_id": "toolu_2", "content": "line 1: missing @startuml"},
        {"type": "text", "text": "No more tool calls. Answer now with the JSON."},
    ]
    # Tools withdrawn by call_structured stay defined (an edited tool list would invalidate the
    # thinking blocks above); tool_choice none forbids new calls.
    assert api.body["tools"] and api.body["tool_choice"] == {"type": "none"}


def test_assistant_turns_without_provider_blocks_are_built_from_text_and_tool_calls():
    api = FakeAPI(streamed([{"type": "text", "text": "{}"}]))
    history = [
        ChatTurn(role="assistant", content="Hello, what should the app do?"),
        ChatTurn(role="user", content="Track tasks"),
        ChatTurn(role="assistant", content="", tool_calls=[ToolCall(id="c1", name="check_plantuml", arguments={"source": "x"})]),
        ChatTurn(role="tool", tool_call_id="c1", content=""),
        ChatTurn(role="assistant", content=""),
    ]
    llm(api).complete(ask(messages=history, tools=[SPEC]))
    sent = api.body["messages"]
    assert sent[0]["role"] == "user"  # the API wants a user turn first
    assert sent[3]["content"] == [{"type": "tool_use", "id": "c1", "name": "check_plantuml", "input": {"source": "x"}}]
    assert sent[4]["content"] == [{"type": "tool_result", "tool_use_id": "c1", "content": "(no output)"}]
    assert sent[5]["content"] == [{"type": "text", "text": "(no answer)"}]
    assert all(b.get("text") != "" for m in sent for b in m["content"])  # empty text blocks are refused by the API
    assert sent[-1]["role"] == "user"  # no assistant prefill on current models


def test_usage_and_cost_are_reported_from_the_price_table():
    api = FakeAPI(streamed([{"type": "text", "text": "{}"}], model="claude-sonnet-5-5", usage={"input_tokens": 1_000_000, "output_tokens": 100_000}))
    reply = llm(api).complete(ask())
    assert reply.usage == {"prompt_tokens": 1_000_000, "completion_tokens": 100_000}
    assert reply.cost_usd == pytest.approx(2.0 + 1.0)  # $2 per million in, $10 per million out


def test_cost_is_unknown_for_a_model_without_a_price():
    api = FakeAPI(streamed([{"type": "text", "text": "{}"}], model="claude-some-future-model"))
    assert llm(api).complete(ask()).cost_usd is None


@pytest.mark.parametrize(
    ("status", "kind", "hint"),
    [
        (401, "authentication_error", "key is wrong"),
        (403, "permission_error", "no access"),
        (404, "not_found_error", "model name"),
        (429, "rate_limit_error", "rate limit"),
        (529, "overloaded_error", "overloaded"),
    ],
)
def test_http_errors_become_llm_errors_with_a_hint(status, kind, hint):
    api = FakeAPI(error(status, "upstream says no", kind))
    with pytest.raises(LLMError, match=rf"Anthropic returned {status} \(.*{hint}.*\): upstream says no"):
        llm(api).complete(ask())


def test_an_openrouter_key_in_the_anthropic_field_is_named():
    with pytest.raises(LLMError, match="OpenRouter key"):
        llm(FakeAPI(error(401, "invalid x-api-key", "authentication_error")), key="sk-or-v1-abc").complete(ask())


def test_network_failure_becomes_an_llm_error():
    def broken(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route", request=request)

    with pytest.raises(LLMError, match="Anthropic request failed"):
        AnthropicLLM("sk-ant-test", MODELS, http_client=httpx2.Client(transport=httpx2.MockTransport(broken)), max_retries=0).complete(ask())


def test_a_refusal_is_an_error_with_its_category():
    api = FakeAPI(streamed([], stop="refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": None}))
    with pytest.raises(LLMError, match="declined.*cyber"):
        llm(api).complete(ask())


def test_after_a_fallback_only_the_continuing_models_tool_calls_count():
    """A fallback block marks where another model took over; tool calls of the declined part are not run
    and its thinking and tool_use blocks are not sent back (refusal fallback rules)."""
    api = FakeAPI(
        streamed(
            [
                {"type": "thinking", "signature": "sig-declined"},
                {"type": "tool_use", "id": "toolu_old", "name": "check_plantuml", "input": {}},
                {"type": "fallback", "from": {"model": "claude-sonnet-5-5"}, "to": {"model": "claude-sonnet-5"}},
                {"type": "tool_use", "id": "toolu_new", "name": "check_plantuml", "input": {"source": "y"}},
            ],
            model="claude-sonnet-5",
            stop="tool_use",
        )
    )
    reply = llm(api).complete(ask(tools=[SPEC]))
    assert [c.id for c in reply.tool_calls] == ["toolu_new"]
    assert [b["type"] for b in reply.provider_content] == ["fallback", "tool_use"]
    assert reply.model == "claude-sonnet-5"


def test_an_empty_key_is_refused():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicLLM("", MODELS)


def test_a_custom_base_url_is_used():
    api = FakeAPI(streamed([{"type": "text", "text": "{}"}]))
    AnthropicLLM("sk-ant-test", MODELS, base_url="https://proxy.example/anthropic", http_client=httpx2.Client(transport=httpx2.MockTransport(api)), max_retries=0).complete(ask())
    assert str(api.requests[0].url).startswith("https://proxy.example/anthropic/v1/messages")
