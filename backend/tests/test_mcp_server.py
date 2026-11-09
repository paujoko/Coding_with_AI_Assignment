"""Wings as an MCP server: the same targeted control as the CLI and the HTTP API, for AI tools."""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from wings.bootstrap import build_container  # noqa: E402
from wings.config import Settings  # noqa: E402
from wings.mcp_server import build_server  # noqa: E402


def call(server, tool, **args):
    result = asyncio.run(server.call_tool(tool, args))
    blocks = result.content if hasattr(result, "content") else result
    return json.loads(blocks[0].text)


def test_tools_drive_a_project_through_requirements(tmp_path):
    server = build_server(build_container(Settings(workspace_dir=tmp_path / "ws")))
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert {"list_projects", "create_project", "run_action", "approve", "get_artifacts", "get_trace", "check_plantuml", "check_consistency"} <= names

    pid = call(server, "create_project", name="Mcp demo")["id"]
    asked = call(server, "run_action", project=pid, phase="requirements", action="start", input={"description": "A todo app"})
    assert asked["status"] == "needs_input" and "Q1" in asked["reply"]
    call(server, "run_action", project=pid, phase="requirements", action="answer", input={"answers": "CLI"})
    assert call(server, "approve", project=pid, phase="requirements")["phases"]["design"] == "ready"
    arts = call(server, "get_artifacts", project=pid, phase="requirements")
    assert arts[0]["id"] == "requirements" and "REQ-001" in arts[0]["text"]


def test_errors_come_back_as_readable_results(tmp_path):
    server = build_server(build_container(Settings(workspace_dir=tmp_path / "ws")))
    out = call(server, "run_action", project="nope", phase="requirements", action="start", input={"description": "x"})
    assert out["error"] and "nope" in out["error"]


def test_uml_checks_are_available_without_a_project(tmp_path):
    server = build_server(build_container(Settings(workspace_dir=tmp_path / "ws")))
    out = call(server, "check_consistency", class_diagram="@startuml\nclass A\n@enduml", sequence_diagrams={"s": "@startuml\nA -> B : go()\n@enduml"})
    assert any("B" in p for p in out["problems"])
