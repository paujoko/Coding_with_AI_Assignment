"""Agents with tools: the model may call deterministic tools before it answers; code runs them."""

from pydantic import BaseModel

from wings.application.agent import LLMAgent
from wings.application.ports import LLMReply, LLMRequest, ToolCall
from wings.application.tools import AgentTool


class Answer(BaseModel):
    verdict: str


class Echo(BaseModel):
    text: str


class FakeLLM:
    """Replies with the queued replies in order and records every request."""

    def __init__(self, replies: list[LLMReply]):
        self.replies = replies
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMReply:
        self.calls.append(request)
        return self.replies.pop(0)


class Ctx:
    def __init__(self, llm):
        self.llm = llm
        self.events: list[tuple[str, str, dict]] = []

    def log(self, kind, summary, data):
        self.events.append((kind, summary, data))


ECHO = AgentTool(name="echo", description="Repeat the text in capitals.", input_model=Echo, run=lambda ctx, p: p.text.upper())


def call(name, **args):
    return LLMReply(text="", model="fake", tool_calls=[ToolCall(id=f"c-{name}", name=name, arguments=args)])


def test_tool_results_go_back_to_the_model_before_the_answer():
    llm = FakeLLM([call("echo", text="hi"), LLMReply(text='{"verdict": "ok"}', model="fake")])
    ctx = Ctx(llm)
    out = LLMAgent("architect", "role", "system").ask(ctx, [], Answer, tools=[ECHO])
    assert out.verdict == "ok"
    assert [t.name for t in llm.calls[0].tools] == ["echo"]
    last = llm.calls[1].messages
    assert last[-2].role == "assistant" and last[-2].tool_calls[0].name == "echo"
    assert (last[-1].role, last[-1].tool_call_id, last[-1].content) == ("tool", "c-echo", "HI")
    kinds = [e[0] for e in ctx.events]
    assert kinds == ["agent.tool_call", "agent.llm_call"]
    assert "echo" in ctx.events[0][1]


def test_unknown_tools_and_bad_arguments_become_messages_not_crashes():
    llm = FakeLLM([call("nope"), call("echo", wrong=1), LLMReply(text='{"verdict": "ok"}', model="fake")])
    LLMAgent("architect", "role", "system").ask(Ctx(llm), [], Answer, tools=[ECHO])
    assert "unknown tool" in llm.calls[1].messages[-1].content
    assert "invalid arguments" in llm.calls[2].messages[-1].content


def test_endless_tool_calls_are_cut_off_and_the_model_must_answer():
    llm = FakeLLM([call("echo", text="a")] * 4 + [LLMReply(text='{"verdict": "done"}', model="fake")])
    out = LLMAgent("architect", "role", "system").ask(Ctx(llm), [], Answer, tools=[ECHO], max_tool_rounds=3)
    assert out.verdict == "done"
    assert llm.calls[-1].tools == []  # the last request offers no tools any more
