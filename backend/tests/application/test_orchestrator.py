from typing import ClassVar

import pytest
from pydantic import BaseModel

from wings.adapters.fs_store import FileSystemStore
from wings.adapters.plantuml import PlantUMLRenderer
from wings.application.orchestrator import ActionFailedError, Orchestrator
from wings.application.phase import ActionOutcome, ActionSpec, PhaseContext, PhaseModule
from wings.application.ports import LLMError
from wings.application.registry import PhaseRegistry
from wings.domain.artifacts import Artifact, ArtifactKind
from wings.domain.errors import InvalidTransitionError, NotFoundError, PhaseLockedError
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S


class Say(BaseModel):
    text: str


class FakePhase(PhaseModule):
    """Produces one artifact per `make`, asks a question on `ask`, fails on `boom`."""

    title: ClassVar[str] = "fake"
    summary: ClassVar[str] = ""

    @property
    def actions(self) -> list[ActionSpec]:
        return [
            ActionSpec(name="make", label="Make", description="", input_model=Say, message_field="text"),
            ActionSpec(name="ask", label="Ask", description=""),
            ActionSpec(name="boom", label="Boom", description=""),
        ]

    def run(self, action: str, payload: BaseModel, ctx: PhaseContext) -> ActionOutcome:
        if action == "boom":
            raise LLMError("provider down")
        if action == "ask":
            return ActionOutcome(status=S.NEEDS_INPUT, reply="Which database?")
        ctx.log("fake.work", "working", {})
        art = Artifact(id=f"{self.id.value}-out", kind=ArtifactKind.DIAGRAM, phase=self.id, title="out", text=payload.text, author="agent:fake")
        return ActionOutcome(status=S.DRAFT, reply="done", artifacts=[art])


def fake(pid: P, requires: list[P]) -> FakePhase:
    return type(f"Fake_{pid.value}", (FakePhase,), {"id": pid, "requires": requires})()


@pytest.fixture
def orch(tmp_path):
    registry = PhaseRegistry([fake(P.REQUIREMENTS, []), fake(P.DESIGN, [P.REQUIREMENTS]), fake(P.REFINEMENT, [P.DESIGN])])
    return Orchestrator(registry, FileSystemStore(tmp_path), llm=None, renderer=PlantUMLRenderer())


def make(orch, pid, phase, text="x"):
    return orch.run_action(pid, phase, "make", {"text": text})


def test_create_project_with_unique_ids(orch):
    a, b = orch.create_project("Todo App"), orch.create_project("Todo App")
    assert (a.id, b.id) == ("todo-app", "todo-app-2")
    assert orch.store.list_events(a.id)[0].kind == "project.created"


def test_action_saves_artifact_sets_status_and_logs(orch):
    pid = orch.create_project("p").id
    result = make(orch, pid, P.REQUIREMENTS, "hello")
    assert result.project.status(P.REQUIREMENTS) is S.DRAFT
    assert result.outcome.artifacts[0].revision == 1
    kinds = [e.kind for e in orch.store.list_events(pid)]
    assert kinds == ["project.created", "action.started", "fake.work", "artifact.saved", "action.finished"]
    msgs = orch.store.list_messages(pid, P.REQUIREMENTS)
    assert [(m.role, m.text) for m in msgs] == [("developer", "hello"), ("agent", "done")]


def test_locked_phase_and_unknown_action(orch):
    pid = orch.create_project("p").id
    with pytest.raises(PhaseLockedError):
        make(orch, pid, P.DESIGN)
    with pytest.raises(NotFoundError):
        orch.run_action(pid, P.REQUIREMENTS, "nope", {})
    with pytest.raises(NotFoundError):
        orch.run_action("missing", P.REQUIREMENTS, "make", {"text": "x"})


def test_needs_input_without_artifact(orch):
    pid = orch.create_project("p").id
    result = orch.run_action(pid, P.REQUIREMENTS, "ask", {})
    assert result.project.status(P.REQUIREMENTS) is S.NEEDS_INPUT
    with pytest.raises(InvalidTransitionError):
        orch.approve(pid, P.REQUIREMENTS)


def test_new_revision_after_approval_stales_dependants(orch):
    pid = orch.create_project("p").id
    make(orch, pid, P.REQUIREMENTS)
    orch.approve(pid, P.REQUIREMENTS)
    make(orch, pid, P.DESIGN)
    result = make(orch, pid, P.REQUIREMENTS, "changed")
    assert result.stale == [P.DESIGN]
    assert result.project.status(P.REQUIREMENTS) is S.DRAFT
    assert result.project.status(P.DESIGN) is S.STALE
    assert "phase.stale" in [e.kind for e in orch.store.list_events(pid)]


def test_developer_edit_is_a_revision_by_the_developer(orch):
    pid = orch.create_project("p").id
    make(orch, pid, P.REQUIREMENTS)
    orch.approve(pid, P.REQUIREMENTS)
    make(orch, pid, P.DESIGN)
    edited, stale = orch.update_artifact(pid, "requirements-out", text="by hand")
    assert (edited.revision, edited.author, edited.text) == (2, "developer", "by hand")
    assert stale == [P.DESIGN]


def test_provider_failure_is_logged_and_wrapped(orch):
    pid = orch.create_project("p").id
    with pytest.raises(ActionFailedError, match="provider down"):
        orch.run_action(pid, P.REQUIREMENTS, "boom", {})
    assert orch.store.list_events(pid)[-1].kind == "phase.error"
    assert orch.project(pid).status(P.REQUIREMENTS) is S.READY


def test_invalid_input_is_rejected_before_running(orch):
    pid = orch.create_project("p").id
    with pytest.raises(ValueError):
        orch.run_action(pid, P.REQUIREMENTS, "make", {"wrong": 1})
