import json

import httpx
import pytest

from wings.adapters.llm_openai import OpenAILLM
from wings.application.ports import ChatTurn, LLMError, LLMRequest

MODELS = {"small": "gpt-s", "mid": "gpt-m", "frontier": "gpt-f"}


def request(tier="mid", json_mode=True) -> LLMRequest:
    return LLMRequest(agent="analyst", system="Reply in JSON.", messages=[ChatTurn(role="user", content="hi")], tier=tier, json_mode=json_mode)


def test_openai_request_shape_and_reply():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"model": "gpt-m-2026", "choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 9}})

    llm = OpenAILLM("sk-test", MODELS, client=httpx.Client(transport=httpx.MockTransport(handler)))
    reply = llm.complete(request())
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["model"] == "gpt-m"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "usage" not in seen["body"]  # an OpenRouter-only field; OpenAI refuses unknown arguments
    assert (reply.text, reply.model, reply.usage, reply.cost_usd) == ("{}", "gpt-m-2026", {"total_tokens": 9}, None)


def test_openai_errors_name_the_provider_and_the_likely_fix():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": {"message": "Incorrect API key"}})))
    with pytest.raises(LLMError, match="OpenAI returned 401.*key"):
        OpenAILLM("sk-bad", MODELS, client=client).complete(request())


def test_budget_errors_and_a_wrong_key_type_get_a_plain_hint():
    from wings.adapters.llm_openrouter import OpenRouterLLM

    def answering(status):
        return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json={"error": {"message": "x"}})))

    with pytest.raises(LLMError, match="budget"):
        OpenRouterLLM("sk-or-v1-abc", MODELS, client=answering(402)).complete(request())
    with pytest.raises(LLMError, match="budget"):
        OpenRouterLLM("sk-or-v1-abc", MODELS, client=answering(403)).complete(request())
    # an OpenRouter key saved as the OpenAI key (Paul's case, s03)
    with pytest.raises(LLMError, match="OpenRouter key"):
        OpenAILLM("sk-or-v1-abc", MODELS, client=answering(401)).complete(request())


def test_long_answers_have_five_minutes():
    """Real runs (s03): the tester's calls took up to about 80 s on average; 180 s left little room."""
    assert OpenAILLM("sk-test", MODELS)._client.timeout.read == 300.0


def test_an_empty_key_is_refused():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAILLM("", MODELS)


def test_json_mode_is_left_out_while_tools_are_offered():
    """Found in a real DeepSeek V4.1 Flash run (s03): with `response_format: json_object` and tools in
    one request, the model never called a tool and wrote the tool's arguments as its answer instead.
    The JSON is still enforced by the schema in the prompt, validation and the retry."""
    from wings.application.ports import ToolSpec

    bodies: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json={"model": "gpt-f", "choices": [{"message": {"content": "{}"}}]})

    llm = OpenAILLM("sk-test", MODELS, client=httpx.Client(transport=httpx.MockTransport(handler)))
    spec = ToolSpec(name="check_coverage", description="Check coverage.", parameters={"type": "object", "properties": {}})
    llm.complete(LLMRequest(agent="architect", system="s", messages=[ChatTurn(role="user", content="hi")], tools=[spec], json_mode=True))
    llm.complete(LLMRequest(agent="architect", system="s", messages=[ChatTurn(role="user", content="hi")], tools=[], json_mode=True))
    assert "response_format" not in bodies[0] and bodies[0]["tools"]
    assert bodies[1]["response_format"] == {"type": "json_object"}  # tools withdrawn: JSON mode is back


def test_tools_are_sent_and_tool_calls_parsed():
    from wings.application.ports import ToolCall, ToolSpec

    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "check_plantuml", "arguments": '{"source": "@startuml\\n@enduml"}'}}]}
        return httpx.Response(200, json={"model": "gpt-m", "choices": [{"message": msg}]})

    llm = OpenAILLM("sk-test", MODELS, client=httpx.Client(transport=httpx.MockTransport(handler)))
    spec = ToolSpec(name="check_plantuml", description="Check a diagram.", parameters={"type": "object", "properties": {"source": {"type": "string"}}})
    history = [
        ChatTurn(role="user", content="hi"),
        ChatTurn(role="assistant", content="", tool_calls=[ToolCall(id="call_0", name="check_plantuml", arguments={"source": "x"})]),
        ChatTurn(role="tool", content="OK", tool_call_id="call_0"),
    ]
    reply = llm.complete(LLMRequest(agent="architect", system="s", messages=history, tools=[spec]))
    assert seen["body"]["tools"] == [{"type": "function", "function": {"name": "check_plantuml", "description": "Check a diagram.", "parameters": spec.parameters}}]
    sent = seen["body"]["messages"]
    assert sent[2]["tool_calls"][0] == {"id": "call_0", "type": "function", "function": {"name": "check_plantuml", "arguments": '{"source": "x"}'}}
    assert sent[3] == {"role": "tool", "tool_call_id": "call_0", "content": "OK"}
    assert reply.tool_calls == [ToolCall(id="call_1", name="check_plantuml", arguments={"source": "@startuml\n@enduml"})]
    assert reply.text == ""
