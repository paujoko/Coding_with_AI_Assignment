from wings.domain.artifacts import Artifact, ArtifactKind
from wings.domain.phases import PhaseId
from wings.domain.trace import coverage


def diagram(name: str, covers: list[str]) -> Artifact:
    return Artifact(id=f"diagram-{name}", kind=ArtifactKind.DIAGRAM, phase=PhaseId.DESIGN, title=name, covers=covers)


def test_coverage_lists_uncovered_in_input_order():
    report = coverage(["REQ-001", "REQ-002", "REQ-003"], [diagram("uc", ["REQ-003"]), diagram("cls", ["REQ-001", "REQ-003"])])
    assert report.uncovered == ["REQ-002"]
    assert report.covered == {"REQ-001": ["diagram-cls"], "REQ-003": ["diagram-uc", "diagram-cls"]}
    assert report.unknown_refs == []


def test_unknown_references_are_reported():
    report = coverage(["REQ-001"], [diagram("uc", ["REQ-001", "REQ-099"])])
    assert report.unknown_refs == ["REQ-099"]


def test_ratio():
    assert coverage([], []).ratio == 1.0
    assert coverage(["REQ-001", "REQ-002"], [diagram("uc", ["REQ-001"])]).ratio == 0.5


def test_trace_view_names_requirements_and_falls_back_to_ids():
    from wings.domain.trace import trace_view

    req = Artifact(
        id="requirements", kind=ArtifactKind.REQUIREMENTS, phase=PhaseId.REQUIREMENTS, title="Requirements",
        content={"requirements": [{"id": "REQ-001", "title": "Add a task"}]}, defines=["REQ-001", "REQ-002"],
    )
    diagram = Artifact(id="diagram-x", kind=ArtifactKind.DIAGRAM, phase=PhaseId.DESIGN, title="Use cases", covers=["REQ-001"])
    view = trace_view([req, diagram])
    assert [(n.id, n.title) for n in view.requirements] == [("REQ-001", "Add a task"), ("REQ-002", "REQ-002")]
    assert [(a.id, a.covers) for a in view.artifacts] == [("diagram-x", ["REQ-001"])]
    assert view.report.uncovered == ["REQ-002"]
