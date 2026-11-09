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


def test_an_empty_key_is_refused():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAILLM("", MODELS)
