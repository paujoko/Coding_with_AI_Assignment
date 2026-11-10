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


# Review findings (2026-11-09)


class SlowPhase(FakePhase):
    """`make` waits on an event so a test can interleave another request."""

    gate = None
    entered = None

    def run(self, action, payload, ctx):
        if action == "make" and self.gate is not None:
            self.entered.set()
            self.gate.wait(timeout=5)
        return super().run(action, payload, ctx)


def test_concurrent_edit_during_action_is_not_lost(tmp_path):
    # Finding 1: an edit made while design was generating got overwritten, leaving unreviewed requirements approved.
    import threading

    slow = type("Slow_design", (SlowPhase,), {"id": P.DESIGN, "requires": [P.REQUIREMENTS]})()
    orch = Orchestrator(PhaseRegistry([fake(P.REQUIREMENTS, []), slow]), FileSystemStore(tmp_path), llm=None, renderer=PlantUMLRenderer())
    pid = orch.create_project("p").id
    make(orch, pid, P.REQUIREMENTS)
    orch.approve(pid, P.REQUIREMENTS)

    slow.gate, slow.entered = threading.Event(), threading.Event()
    worker = threading.Thread(target=make, args=(orch, pid, P.DESIGN))
    worker.start()
    assert slow.entered.wait(5)  # design is now inside its (slow) LLM work
    editor = threading.Thread(target=orch.update_artifact, args=(pid, "requirements-out"), kwargs={"text": "edited"})
    editor.start()
    slow.gate.set()
    worker.join(5)
    editor.join(5)

    project = orch.project(pid)
    assert project.status(P.REQUIREMENTS) is S.DRAFT  # the edit counts: requirements need review again
    assert project.status(P.DESIGN) is S.STALE  # and the design built on the old version is stale


def test_save_from_another_process_is_detected(orch):
    from wings.domain.errors import ConflictError

    pid = orch.create_project("p").id
    mine = orch.project(pid)
    other = orch.project(pid)
    orch.store.save_project(other)  # someone else saved in between
    with pytest.raises(ConflictError):
        orch.store.save_project(mine)


def test_wing_cannot_approve_itself(orch):
    class SelfApproving(FakePhase):
        def run(self, action, payload, ctx):
            return ActionOutcome(status=S.APPROVED)

    phase = type("SA", (SelfApproving,), {"id": P.REQUIREMENTS, "requires": []})()
    o = Orchestrator(PhaseRegistry([phase]), orch.store, llm=None, renderer=orch.renderer)
    pid = o.create_project("self").id
    with pytest.raises(InvalidTransitionError):
        o.run_action(pid, P.REQUIREMENTS, "make", {"text": "x"})
    assert o.project(pid).status(P.REQUIREMENTS) is S.READY


def test_wing_gets_read_only_view(orch):
    class Sneaky(FakePhase):
        def run(self, action, payload, ctx):
            ctx.project.set_status(P.REQUIREMENTS, S.APPROVED)  # mutates only the wing's copy
            assert not hasattr(ctx.store, "save_project")
            return ActionOutcome(status=S.NEEDS_INPUT, reply="?")

    phase = type("SN", (Sneaky,), {"id": P.REQUIREMENTS, "requires": []})()
    o = Orchestrator(PhaseRegistry([phase]), orch.store, llm=None, renderer=orch.renderer)
    pid = o.create_project("sneaky").id
    assert o.run_action(pid, P.REQUIREMENTS, "make", {"text": "x"}).project.status(P.REQUIREMENTS) is S.NEEDS_INPUT


def test_failed_action_keeps_no_developer_message_and_writes_no_artifacts(orch):
    pid = orch.create_project("p").id
    with pytest.raises(ActionFailedError):
        orch.run_action(pid, P.REQUIREMENTS, "boom", {})
    assert orch.store.list_messages(pid) == []

    class BadPath(FakePhase):
        def run(self, action, payload, ctx):
            ok = Artifact(id="a-ok", kind=ArtifactKind.DIAGRAM, phase=self.id, title="ok", text="x", path="ok.txt")
            bad = ok.model_copy(update={"id": "b-bad", "path": "../escape.txt"})
            return ActionOutcome(status=S.DRAFT, artifacts=[ok, bad])

    phase = type("BP", (BadPath,), {"id": P.REQUIREMENTS, "requires": []})()
    o = Orchestrator(PhaseRegistry([phase]), orch.store, llm=None, renderer=orch.renderer)
    pid2 = o.create_project("badpath").id
    with pytest.raises(ActionFailedError):
        o.run_action(pid2, P.REQUIREMENTS, "make", {"text": "x"})
    assert o.store.list_artifacts(pid2) == []  # the valid one was not written either
    assert o.store.list_events(pid2)[-1].kind == "phase.error"


def test_a_second_action_while_an_agent_works_is_refused_and_the_running_one_is_visible(tmp_path):
    """Real run (s03): 'Write tests' was sent twice; the second waited behind the first and ran again
    (6 more minutes, double cost). Now it is refused, and the project says what is running."""
    import threading

    from wings.domain.errors import ConflictError

    slow = type("Slow_requirements", (SlowPhase,), {"id": P.REQUIREMENTS, "requires": []})()
    orch = Orchestrator(PhaseRegistry([slow]), FileSystemStore(tmp_path), llm=None, renderer=PlantUMLRenderer())
    pid = orch.create_project("p").id
    assert orch.running(pid) is None

    slow.gate, slow.entered = threading.Event(), threading.Event()
    worker = threading.Thread(target=make, args=(orch, pid, P.REQUIREMENTS))
    worker.start()
    assert slow.entered.wait(5)
    running = orch.running(pid)
    assert (running["phase"], running["action"], running["label"]) == ("requirements", "make", "Make")
    assert running["started_at"]
    with pytest.raises(ConflictError, match="already working"):
        make(orch, pid, P.REQUIREMENTS)
    slow.gate.set()
    worker.join(5)
    assert orch.running(pid) is None
    assert make(orch, pid, P.REQUIREMENTS).outcome.reply == "done"  # free again


def test_a_failed_action_does_not_leave_the_project_busy(orch):
    pid = orch.create_project("p").id
    with pytest.raises(ActionFailedError):
        orch.run_action(pid, P.REQUIREMENTS, "boom", {})
    assert orch.running(pid) is None
