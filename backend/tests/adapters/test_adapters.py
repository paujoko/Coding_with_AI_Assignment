import json

import httpx
import pytest

from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.llm_openrouter import OpenRouterLLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.application.ports import ChatTurn, LLMError, LLMRequest
from wings.domain.activity import Event, Message, Role
from wings.domain.artifacts import Artifact, ArtifactKind
from wings.domain.errors import NotFoundError
from wings.domain.phases import PhaseId
from wings.domain.project import Project

DEPS = {PhaseId.REQUIREMENTS: [], PhaseId.DESIGN: [PhaseId.REQUIREMENTS]}


@pytest.fixture
def store(tmp_path):
    s = FileSystemStore(tmp_path)
    s.save_project(Project.new("Todo", DEPS))
    return s


def req_artifact(text: str) -> Artifact:
    return Artifact(id="requirements", kind=ArtifactKind.REQUIREMENTS, phase=PhaseId.REQUIREMENTS, title="R", text=text, path="requirements.md")


def test_project_round_trip(store):
    assert store.load_project("todo").name == "Todo"
    assert [p.id for p in store.list_projects()] == ["todo"]
    with pytest.raises(NotFoundError):
        store.load_project("missing")
    with pytest.raises(NotFoundError):
        store.load_project("../etc")


def test_artifact_revisions_and_materialized_file(store, tmp_path):
    first = store.save_artifact("todo", req_artifact("v1"))
    second = store.save_artifact("todo", req_artifact("v2"))
    assert (first.revision, second.revision) == (1, 2)
    assert store.get_artifact("todo", "requirements").text == "v2"
    assert [a.text for a in store.artifact_history("todo", "requirements")] == ["v1", "v2"]
    assert (tmp_path / "todo" / "files" / "requirements.md").read_text(encoding="utf-8") == "v2"
    assert store.list_artifacts("todo", PhaseId.DESIGN) == []


def test_artifact_path_cannot_escape_workspace(store):
    bad = req_artifact("x").model_copy(update={"path": "../../evil.md"})
    with pytest.raises(ValueError):
        store.save_artifact("todo", bad)


def test_events_are_numbered_and_filterable(store):
    for i in range(3):
        store.append_event("todo", Event(kind="k", summary=str(i)))
    assert [e.seq for e in store.list_events("todo")] == [1, 2, 3]
    assert [e.summary for e in store.list_events("todo", after=2)] == ["2"]


def test_messages_filter_by_phase(store):
    store.append_message("todo", Message(phase=PhaseId.REQUIREMENTS, role=Role.DEVELOPER, text="hi"))
    store.append_message("todo", Message(phase=PhaseId.DESIGN, role=Role.AGENT, text="yo"))
    assert [m.text for m in store.list_messages("todo", PhaseId.DESIGN)] == ["yo"]


def request(agent: str, json_mode: bool = True, earlier_replies: int = 0) -> LLMRequest:
    turns = [ChatTurn(role="user", content="u")]
    for _ in range(earlier_replies):
        turns += [ChatTurn(role="assistant", content="a"), ChatTurn(role="user", content="u")]
    return LLMRequest(agent=agent, system="s", messages=turns, json_mode=json_mode)


def test_scripted_llm_picks_reply_by_conversation_stage():
    llm = ScriptedLLM({"a": ["1", "2"], "a:chat": ["talk"]})
    assert [llm.complete(request("a", earlier_replies=n)).text for n in (0, 1, 2, 0)] == ["1", "2", "2", "1"]
    assert llm.complete(request("a", json_mode=False)).text == "talk"
    # A fresh instance (e.g. a new CLI process) answers the same stage the same way.
    assert ScriptedLLM({"a": ["1", "2"]}).complete(request("a", earlier_replies=1)).text == "2"
    with pytest.raises(LLMError):
        llm.complete(request("unknown"))


def test_scripted_llm_from_file_accepts_objects(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"a": [{"x": 1}]}), encoding="utf-8")
    assert json.loads(ScriptedLLM.from_file(path).complete(request("a")).text) == {"x": 1}


def test_openrouter_request_shape_and_reply():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"model": "m-mid", "choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 7, "cost": 0.001}})

    llm = OpenRouterLLM("key", {"small": "m-s", "mid": "m-mid", "frontier": "m-f"}, client=httpx.Client(transport=httpx.MockTransport(handler)))
    reply = llm.complete(request("a"))
    assert seen["auth"] == "Bearer key"
    assert seen["body"]["model"] == "m-mid"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "s"}
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert (reply.text, reply.usage, reply.cost_usd) == ("{}", {"total_tokens": 7}, 0.001)


def test_openrouter_http_error_becomes_llm_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429, text="rate limited")))
    llm = OpenRouterLLM("key", {"small": "a", "mid": "b", "frontier": "c"}, client=client)
    with pytest.raises(LLMError, match="429"):
        llm.complete(request("a"))


def test_renderer_without_backend_returns_none(tmp_path):
    r = PlantUMLRenderer(jar=tmp_path / "missing.jar")
    assert not r.available
    assert r.render_svg("@startuml\nA -> B\n@enduml") is None


@pytest.mark.parametrize("bad", [r"..\..\escaped.txt", "C:/evil.txt", "/abs.txt", "a/../../b.txt", r"design\x.puml"])
def test_artifact_paths_are_confined_to_the_workspace(store, tmp_path, bad):
    # Review finding 2: backslashes slipped past a PurePosixPath check on Windows.
    with pytest.raises(ValueError):
        store.save_artifact("todo", req_artifact("x").model_copy(update={"path": bad}))
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "todo" / "artifacts" / "requirements").exists()  # nothing half-written


def test_retired_artifact_removes_its_file(store, tmp_path):
    # Review finding 7: retired diagrams (later: deleted source files) must not linger on disk.
    store.save_artifact("todo", req_artifact("v1"))
    store.save_artifact("todo", req_artifact("v1").model_copy(update={"retired": True}))
    assert not (tmp_path / "todo" / "files" / "requirements.md").exists()
    assert store.get_artifact("todo", "requirements").retired


def test_check_artifact_rejects_unsafe_ids_without_writing(store, tmp_path):
    with pytest.raises(ValueError):
        store.check_artifact("todo", req_artifact("x").model_copy(update={"id": "Source/App.py"}))
    assert not (tmp_path / "todo" / "artifacts").exists()


def test_openrouter_non_json_reply_becomes_llm_error():
    # Review finding 8: a non-JSON 200 response surfaced as HTTP 422 without a phase.error event.
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>gateway</html>")))
    llm = OpenRouterLLM("key", {"small": "a", "mid": "b", "frontier": "c"}, client=client)
    with pytest.raises(LLMError, match="Unexpected"):
        llm.complete(request("a"))
