"""P4 Code generation through the orchestrator with the scripted mock."""

import copy

import pytest

from wings.domain.errors import InvalidInputError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S


def test_generate_writes_files_that_match_the_refined_design(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = walk(orch, P.CODEGEN)
    result = orch.run_action(pid, P.CODEGEN, "generate", {})
    ids = sorted(a.id for a in result.outcome.artifacts)
    assert "source-todo-service-py" in ids and len(ids) == 6
    assert result.outcome.data["drift"] == []
    assert result.project.status(P.CODEGEN) is S.DRAFT
    service = orch.store.get_artifact(pid, "source-todo-service-py")
    assert service.path == "app/todo/service.py" and "REQ-003" in service.covers
    tools = {e.data["tool"] for e in orch.store.list_events(pid) if e.kind == "agent.tool_call" and e.data["agent"] == "coder"}
    assert tools == {"check_python", "compare_with_design"}


def test_code_that_differs_from_the_design_is_reported(make_orchestrator, demo_script, walk):
    script = copy.deepcopy(demo_script)
    service = next(f for f in script["coder"][0]["files"] if f["path"] == "todo/service.py")
    service["content"] = service["content"].replace("def delete(", "def remove(")
    orch = make_orchestrator(script)
    pid = walk(orch, P.CODEGEN)
    result = orch.run_action(pid, P.CODEGEN, "generate", {})
    assert "TaskService.delete() is in the class diagram but not in the code." in result.outcome.data["drift"]
    assert "TaskService.remove() is in the code but not in the class diagram." in result.outcome.reply


def test_code_that_does_not_parse_is_refused_and_retried(make_orchestrator, demo_script, walk):
    from wings.application.orchestrator import ActionFailedError

    script = copy.deepcopy(demo_script)
    script["coder"][0]["files"][0]["content"] = "def broken(:\n"
    orch = make_orchestrator(script)
    pid = walk(orch, P.CODEGEN)
    with pytest.raises(ActionFailedError, match="line 1"):
        orch.run_action(pid, P.CODEGEN, "generate", {})
    assert orch.store.list_artifacts(pid, P.CODEGEN) == []


def test_developer_edits_are_checked_and_make_later_phases_stale(make_orchestrator, demo_script, walk):
    orch = make_orchestrator(demo_script)
    pid = walk(orch, P.CODEGEN)
    orch.run_action(pid, P.CODEGEN, "generate", {})
    with pytest.raises(InvalidInputError, match="line"):
        orch.update_artifact(pid, "source-todo-models-py", text="class (:")
    saved, _ = orch.update_artifact(pid, "source-todo-models-py", text='"""Edited."""\n')
    assert saved.author == "developer" and saved.revision == 2


def test_paths_that_would_share_an_artifact_id_are_refused():
    # Review round 7, finding 3: todo/__main__.py and todo/main.py both became source-todo-main-py.
    from pydantic import ValidationError

    from wings.phases.codegen.schema import CoderOutput

    files = [{"path": p, "purpose": "", "content": "x = 1\n"} for p in ("todo/__main__.py", "todo/main.py")]
    with pytest.raises(ValidationError, match="same file"):
        CoderOutput(notes="", run="python -m todo", files=files)
