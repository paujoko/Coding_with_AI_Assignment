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


def test_a_repeated_identical_tool_call_is_answered_from_memory():
    """Found in a real run (s03): the tester re-checked the same, already valid files every round."""
    runs = []
    counting = AgentTool(name="echo", description="d", input_model=Echo, run=lambda ctx, p: runs.append(p.text) or p.text.upper())
    llm = FakeLLM([call("echo", text="a"), call("echo", text="a"), LLMReply(text='{"verdict": "ok"}', model="fake")])
    LLMAgent("tester", "role", "system").ask(Ctx(llm), [], Answer, tools=[counting])
    assert runs == ["a"]
    assert "already" in llm.calls[2].messages[-1].content and "A" in llm.calls[2].messages[-1].content


def test_usage_and_cost_of_every_call_are_summed():
    def reply(text, calls=None):
        return LLMReply(text=text, model="fake", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, cost_usd=0.01, tool_calls=calls or [])

    first = reply("", [ToolCall(id="c1", name="echo", arguments={"text": "x"})])
    llm = FakeLLM([first, reply('{"verdict": "ok"}')])
    ctx = Ctx(llm)
    LLMAgent("tester", "role", "system").ask(ctx, [], Answer, tools=[ECHO])
    data = ctx.events[-1][2]
    assert data["usage"]["total_tokens"] == 30 and abs(data["cost_usd"] - 0.02) < 1e-9


def test_a_failed_answer_still_logs_what_it_cost():
    import pytest

    from wings.application.structured import LLMOutputError

    bad = [LLMReply(text="nope", model="fake", cost_usd=0.01) for _ in range(3)]
    ctx = Ctx(FakeLLM(bad))
    with pytest.raises(LLMOutputError):
        LLMAgent("deployer", "role", "system").ask(ctx, [], Answer)
    kind, summary, data = ctx.events[-1]
    assert kind == "agent.llm_failed" and data["attempts"] == 3 and abs(data["cost_usd"] - 0.03) < 1e-9
    assert "Deployer" in summary
