"""Change propagation through the MCP server and the CLI's text view of a change."""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from wings.bootstrap import build_container  # noqa: E402
from wings.cli import _change  # noqa: E402
from wings.config import Settings  # noqa: E402
from wings.domain.phases import PhaseId as P  # noqa: E402
from wings.mcp_server import build_server  # noqa: E402


def call(server, tool, **args):
    result = asyncio.run(server.call_tool(tool, args))
    blocks = result.content if hasattr(result, "content") else result
    return json.loads(blocks[0].text)


def test_an_ai_client_can_list_and_advance_a_change(tmp_path, walk):
    container = build_container(Settings(workspace_dir=tmp_path / "ws"))
    server = build_server(container)
    pid = walk(container.orchestrator, P.MAINTENANCE)
    assert call(server, "list_changes", project=pid) == []
    call(server, "run_action", project=pid, phase="maintenance", action="change", input={"request": "Tasks need a priority"})
    [change] = call(server, "list_changes", project=pid)
    assert change["state"] == "open" and change["next"]["phase"] == "requirements"

    step = call(server, "advance_change", project=pid, number=1)
    assert step["approved"] == "requirements" and step["stopped_reason"] is None
    assert step["phases"]["requirements"] == "approved" and step["phases"]["design"] == "stale"
    assert step["change"]["receipt"][0]["updated"][0]["id"] == "requirements"
    assert "error" in call(server, "advance_change", project=pid, number=9)

    text = _change(container.orchestrator.changes(pid)[0])
    assert "Change 1 [open]" in text and "updated requirements r1 -> r2" in text and "next: design" in text
