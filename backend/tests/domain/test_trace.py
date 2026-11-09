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
