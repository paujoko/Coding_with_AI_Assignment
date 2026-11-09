"""Documents the developer attaches: stored per project, referenced by messages, read by the agents."""

import pytest

from wings.adapters.documents import DocumentTextExtractor
from wings.adapters.fs_store import FileSystemStore
from wings.adapters.llm_mock import ScriptedLLM
from wings.adapters.plantuml import PlantUMLRenderer
from wings.application.orchestrator import MAX_ATTACHMENT_BYTES, Orchestrator
from wings.bootstrap import build_registry
from wings.domain.errors import InvalidInputError
from wings.domain.phases import PhaseId as P
from conftest import as_text


@pytest.fixture
def setup(tmp_path, demo_script):
    llm = ScriptedLLM({agent: [as_text(r) for r in replies] for agent, replies in demo_script.items()})
    orch = Orchestrator(build_registry(), FileSystemStore(tmp_path / "ws"), llm, PlantUMLRenderer(), extractor=DocumentTextExtractor())
    return orch, llm, orch.create_project("Docs").id


def test_attachment_is_stored_and_logged(setup):
    orch, _, pid = setup
    att = orch.add_attachment(pid, "brief.md", "text/markdown", b"# Brief\nA booking tool for rooms.")
    assert att.id == "att-001" and att.text.startswith("# Brief") and att.size == 33
    events = orch.store.list_events(pid)
    assert events[-1].kind == "attachment.added" and "brief.md" in events[-1].summary


def test_too_large_or_empty_files_are_refused(setup):
    orch, _, pid = setup
    with pytest.raises(InvalidInputError, match="MB"):
        orch.add_attachment(pid, "big.txt", "text/plain", b"x" * (MAX_ATTACHMENT_BYTES + 1))
    with pytest.raises(InvalidInputError, match="empty"):
        orch.add_attachment(pid, "empty.txt", "text/plain", b"")


def test_the_analyst_reads_attached_documents(setup):
    orch, llm, pid = setup
    att = orch.add_attachment(pid, "brief.md", "text/markdown", b"Rooms are booked per hour.")
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "A booking tool"}, attachments=[att.id])

    said = orch.store.list_messages(pid, P.REQUIREMENTS)[0]
    assert said.data["attachments"] == [{"id": "att-001", "name": "brief.md"}]
    prompt = "\n".join(t.content for t in llm.calls[-1].messages)
    assert "brief.md" in prompt and "Rooms are booked per hour." in prompt

    # Later turns in the same phase still see the document.
    orch.run_action(pid, P.REQUIREMENTS, "answer", {"answers": "CLI"})
    assert "Rooms are booked per hour." in "\n".join(t.content for t in llm.calls[-1].messages)


def test_documents_alone_are_a_message(setup):
    orch, _, pid = setup
    att = orch.add_attachment(pid, "brief.md", "text/markdown", b"Rooms")
    orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "See the brief"}, attachments=[att.id])
    orch.run_action(pid, P.REQUIREMENTS, "discuss", {"question": "What is unclear?"}, attachments=[att.id])
    assert len(orch.store.list_messages(pid, P.REQUIREMENTS)) == 4


def test_unknown_attachment_ids_are_refused_before_anything_runs(setup):
    orch, llm, pid = setup
    with pytest.raises(InvalidInputError, match="att-404"):
        orch.run_action(pid, P.REQUIREMENTS, "start", {"description": "x"}, attachments=["att-404"])
    assert llm.calls == [] and orch.store.list_messages(pid) == []
