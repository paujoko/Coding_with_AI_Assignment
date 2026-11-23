"""Change tracking: baseline, progress, next step and receipt are computed by code from artifact revisions."""

from wings.domain.artifacts import Artifact, ArtifactKind
from wings.domain.change import ChangeStep, next_step, progress, receipt, receipt_markdown, take_baseline
from wings.domain.phases import PhaseId as P
from wings.domain.phases import PhaseStatus as S
from wings.domain.project import Project

CHAIN = {
    P.REQUIREMENTS: [],
    P.DESIGN: [P.REQUIREMENTS],
    P.REFINEMENT: [P.DESIGN],
    P.CODEGEN: [P.REFINEMENT],
    P.TESTING: [P.CODEGEN],
    P.DEPLOYMENT: [P.TESTING],
    P.MAINTENANCE: [P.DEPLOYMENT],
}
TRACKED = [p for p in CHAIN if p is not P.MAINTENANCE]
KIND = {
    P.REQUIREMENTS: ArtifactKind.REQUIREMENTS,
    P.DESIGN: ArtifactKind.DIAGRAM,
    P.REFINEMENT: ArtifactKind.DIAGRAM,
    P.CODEGEN: ArtifactKind.SOURCE_FILE,
    P.TESTING: ArtifactKind.TEST_FILE,
    P.DEPLOYMENT: ArtifactKind.DEPLOYMENT_FILE,
}
REVISE = ChangeStep(phase=P.REQUIREMENTS, action="revise", input={"feedback": "Add a priority"}, label="Update the requirements")
FIX = ChangeStep(phase=P.CODEGEN, action="revise", input={"feedback": "Compare numbers"}, label="Send the fix")


def art(phase: P, name: str, revision: int = 1, text: str = "v1", retired: bool = False) -> Artifact:
    return Artifact(id=f"{phase.value}-{name}", kind=KIND[phase], phase=phase, title=name, revision=revision, text=text, path=f"{phase.value}/{name}", retired=retired)


def finished() -> tuple[Project, list[Artifact]]:
    """Every phase approved, one artifact each: the moment a change is requested."""
    project = Project.new("Todo", CHAIN)
    for ph in TRACKED:
        project.set_status(ph, S.DRAFT)
        project.approve(ph)
    return project, [art(ph, "a") for ph in TRACKED]


def bump(artifacts: list[Artifact], phase: P, text: str = "v2") -> list[Artifact]:
    return [a.model_copy(update={"revision": a.revision + 1, "text": text}) if a.phase is phase else a for a in artifacts]


def states(project, baseline, artifacts, first=REVISE) -> dict[str, str]:
    return {p.phase.value: p.state for p in progress(project, TRACKED, baseline, artifacts, first).phases}


def test_baseline_holds_revision_and_retired_flag_of_every_artifact():
    _, artifacts = finished()
    artifacts.append(art(P.CODEGEN, "old", revision=3, retired=True))
    base = take_baseline(artifacts)
    assert base["design-a"].revision == 1 and not base["design-a"].retired
    assert base["codegen-old"].revision == 3 and base["codegen-old"].retired
    assert base["design-a"].digest


def test_before_the_first_step_the_first_phase_is_current_and_the_rest_waits():
    project, artifacts = finished()
    base = take_baseline(artifacts)
    result = progress(project, TRACKED, base, artifacts, REVISE)
    assert not result.started and not result.complete
    assert result.current is P.REQUIREMENTS
    assert [p.state for p in result.phases] == ["current", "waiting", "waiting", "waiting", "waiting", "waiting"]
    assert (result.done, result.total) == (0, 6)
    step = next_step(result, project, REVISE, [], None)
    assert (step.kind, step.phase, step.action, step.input) == ("run", P.REQUIREMENTS, "revise", {"feedback": "Add a priority"})


def test_a_bug_leaves_the_phases_before_the_code_untouched():
    project, artifacts = finished()
    base = take_baseline(artifacts)
    result = progress(project, TRACKED, base, artifacts, FIX)
    assert [p.state for p in result.phases] == ["untouched", "untouched", "untouched", "current", "waiting", "waiting"]
    assert (result.done, result.total) == (0, 3)


def test_after_the_first_step_the_changed_phase_waits_for_approval_then_the_next_is_current():
    project, artifacts = finished()
    base = take_baseline(artifacts)
    artifacts = bump(artifacts, P.REQUIREMENTS)
    project.mark_changed(P.REQUIREMENTS)
    result = progress(project, TRACKED, base, artifacts, REVISE)
    assert result.started and result.current is P.REQUIREMENTS
    assert next_step(result, project, REVISE, [], None).kind == "approve"

    project.approve(P.REQUIREMENTS)
    result = progress(project, TRACKED, base, artifacts, REVISE)
    assert [p.state for p in result.phases] == ["done", "current", "waiting", "waiting", "waiting", "waiting"]
    assert (result.done, result.total) == (1, 6)
    refresh = [ChangeStep(phase=P.DESIGN, action="revise", input={"feedback": "why"}, label="Revise")]
    step = next_step(result, project, REVISE, refresh, None)
    assert (step.kind, step.phase, step.action, step.input, len(step.steps)) == ("run", P.DESIGN, "revise", {"feedback": "why"}, 1)


def test_a_stale_phase_without_a_refresh_step_and_a_failed_gate_block_with_a_reason():
    project, artifacts = finished()
    base = take_baseline(artifacts)
    artifacts = bump(artifacts, P.REQUIREMENTS)
    project.mark_changed(P.REQUIREMENTS)
    project.approve(P.REQUIREMENTS)
    result = progress(project, TRACKED, base, artifacts, REVISE)
    step = next_step(result, project, REVISE, [], None)
    assert step.kind == "blocked" and step.reason

    artifacts = bump(artifacts, P.DESIGN)
    project.mark_changed(P.DESIGN)
    result = progress(project, TRACKED, base, artifacts, REVISE)
    step = next_step(result, project, REVISE, [], "No diagram covers REQ-006.")
    assert (step.kind, step.reason) == ("blocked", "No diagram covers REQ-006.")


def test_open_questions_ask_for_input():
    project, artifacts = finished()
    base = take_baseline(artifacts)
    project.set_status(P.REQUIREMENTS, S.NEEDS_INPUT)
    result = progress(project, TRACKED, base, artifacts, REVISE)
    step = next_step(result, project, REVISE, [], None)
    assert step.kind == "input" and step.phase is P.REQUIREMENTS and step.reason


def test_complete_when_every_phase_is_approved_again():
    project, artifacts = finished()
    base = take_baseline(artifacts)
    for ph in TRACKED:
        artifacts = bump(artifacts, ph)
        project.mark_changed(ph)
        project.approve(ph)
    result = progress(project, TRACKED, base, artifacts, REVISE)
    assert result.complete and result.current is None
    assert [p.state for p in result.phases] == ["done"] * 6
    assert next_step(result, project, REVISE, [], None) is None


def test_a_phase_approved_again_without_a_new_revision_counts_as_untouched():
    project, artifacts = finished()
    base = take_baseline(artifacts)
    artifacts = bump(artifacts, P.CODEGEN)
    project.mark_changed(P.CODEGEN)
    for ph in (P.CODEGEN, P.TESTING, P.DEPLOYMENT):
        project.approve(ph)
    assert states(project, base, artifacts, FIX) == {
        "requirements": "untouched", "design": "untouched", "refinement": "untouched", "codegen": "done", "testing": "untouched", "deployment": "untouched",
    }


def test_receipt_lists_updated_added_and_removed_artifacts_per_phase():
    _, artifacts = finished()
    artifacts.append(art(P.CODEGEN, "gone"))
    artifacts.append(art(P.TESTING, "same"))
    base = take_baseline(artifacts)
    after = bump(artifacts, P.REQUIREMENTS)
    after = [a.model_copy(update={"revision": 2, "retired": True}) if a.id == "codegen-gone" else a for a in after]
    after = [a.model_copy(update={"revision": 2}) if a.id == "testing-same" else a for a in after]  # saved again, same text
    after.append(art(P.CODEGEN, "new"))
    after.append(art(P.DEPLOYMENT, "short-lived", retired=True))  # added and retired inside the change
    result = {r.phase: r for r in receipt(base, after, TRACKED)}

    req = result[P.REQUIREMENTS].updated[0]
    assert (req.id, req.before, req.after, req.changed, req.path, req.kind) == ("requirements-a", 1, 2, True, "requirements/a", "requirements")
    assert [a.id for a in result[P.CODEGEN].added] == ["codegen-new"] and result[P.CODEGEN].added[0].before is None
    assert [(a.id, a.before, a.after) for a in result[P.CODEGEN].removed] == [("codegen-gone", 1, 2)]
    same = result[P.TESTING].updated[0]
    assert (same.id, same.changed) == ("testing-same", False)
    assert result[P.DESIGN].updated == [] and result[P.DESIGN].count == 0
    assert result[P.DEPLOYMENT].count == 0
    assert [r.phase for r in receipt(base, after, TRACKED)] == TRACKED


def test_receipt_markdown_names_every_touched_artifact():
    _, artifacts = finished()
    base = take_baseline(artifacts)
    text = receipt_markdown(receipt(base, bump(artifacts, P.CODEGEN), TRACKED), {P.CODEGEN: "Code generation"})
    assert "Code generation" in text and "codegen/a" in text and "revision 1 -> 2" in text
