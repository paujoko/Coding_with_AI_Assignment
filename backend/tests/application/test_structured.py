import pytest
from pydantic import BaseModel

from wings.application.ports import ChatTurn, LLMReply, LLMRequest
from wings.application.structured import LLMOutputError, call_structured, extract_json


class Answer(BaseModel):
    value: int


class Replies:
    def __init__(self, *texts: str):
        self.texts = list(texts)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMReply:
        self.requests.append(request)
        return LLMReply(text=self.texts.pop(0), model="fake")


REQ = LLMRequest(agent="t", system="sys", messages=[ChatTurn(role="user", content="hi")])


def test_extract_json_from_fence_and_prose():
    assert extract_json('Sure:\n```json\n{"value": 1}\n```') == '{"value": 1}'
    assert extract_json('Here {"value": 2} done') == '{"value": 2}'


def test_parses_and_puts_schema_into_system_prompt():
    llm = Replies('{"value": 3}')
    parsed, replies = call_structured(llm, REQ, Answer)
    assert parsed.value == 3 and len(replies) == 1
    assert '"value"' in llm.requests[0].system


def test_retries_once_with_the_error_then_succeeds():
    llm = Replies('{"value": "x"}', '{"value": 4}')
    parsed, replies = call_structured(llm, REQ, Answer)
    assert parsed.value == 4 and len(replies) == 2
    retry = llm.requests[1].messages
    assert retry[-2].role == "assistant" and "not valid" in retry[-1].content


def test_gives_up_after_retries():
    llm = Replies("nope", "again nope", "still nope")
    with pytest.raises(LLMOutputError) as err:
        call_structured(llm, REQ, Answer)
    assert err.value.raw == "still nope"


class Deploy(BaseModel):
    value: int
    doc: str


def test_a_json_reply_with_a_code_fence_inside_a_string_is_read_whole():
    """Found in a real run (s03): DEPLOY.md inside the JSON held a ```bash block, and the fence
    search picked that block instead of the JSON."""
    import json

    text = json.dumps({"value": 5, "doc": "Build:\n```bash\n./run.sh build\n```\nDone."})
    assert extract_json(text) == text
    parsed, _ = call_structured(Replies(text), REQ, Deploy)
    assert parsed.doc.startswith("Build:")


def test_an_empty_reply_is_named_as_such_and_retried_twice():
    """Found in a real run (s03): DeepSeek returned empty content twice in a row."""
    llm = Replies("", "", '{"value": 1}')
    parsed, replies = call_structured(llm, REQ, Answer)
    assert parsed.value == 1 and len(replies) == 3
    assert "empty" in llm.requests[1].messages[-1].content


def test_the_final_error_is_short_and_keeps_every_reply():
    llm = Replies("nope", "", '{"value": "x"}')
    with pytest.raises(LLMOutputError) as err:
        call_structured(llm, REQ, Answer)
    message = str(err.value)
    assert "T's answer could not be used after 3 attempts" in message
    assert "value" in message and "pydantic.dev" not in message and "\n" not in message
    assert len(err.value.replies) == 3
