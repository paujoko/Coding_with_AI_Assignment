"""Trace graph checks. Deterministic on purpose: an LLM may propose links, code verifies them."""

from collections.abc import Iterable

from pydantic import BaseModel

from wings.domain.artifacts import Artifact, ArtifactKind


class CoverageReport(BaseModel):
    covered: dict[str, list[str]]  # requirement id -> artifact ids covering it
    uncovered: list[str]
    unknown_refs: list[str]  # ids referenced by artifacts that do not exist

    @property
    def ratio(self) -> float:
        total = len(self.covered) + len(self.uncovered)
        return 1.0 if total == 0 else len(self.covered) / total


def requirement_coverage(artifacts: list[Artifact]) -> CoverageReport:
    """Coverage of every requirement ID defined by a requirements artifact, by all other artifacts."""
    live = [a for a in artifacts if not a.retired]
    defined = [rid for a in live if a.kind is ArtifactKind.REQUIREMENTS for rid in a.defines]
    return coverage(defined, [a for a in live if a.kind is not ArtifactKind.REQUIREMENTS])


def coverage(requirement_ids: list[str], artifacts: Iterable[Artifact]) -> CoverageReport:
    known = set(requirement_ids)
    covered: dict[str, list[str]] = {rid: [] for rid in requirement_ids}
    unknown: list[str] = []
    for artifact in artifacts:
        for ref in artifact.covers:
            if ref in known:
                covered[ref].append(artifact.id)
            elif ref not in unknown:
                unknown.append(ref)
    return CoverageReport(
        covered={rid: ids for rid, ids in covered.items() if ids},
        uncovered=[rid for rid in requirement_ids if not covered[rid]],
        unknown_refs=unknown,
    )


class TraceNode(BaseModel):
    id: str
    title: str


class TraceArtifact(BaseModel):
    id: str
    title: str
    phase: str
    kind: str
    covers: list[str]


class TraceView(BaseModel):
    """Coverage plus the names a person needs to read it (requirement and artifact titles)."""

    report: CoverageReport
    requirements: list[TraceNode]
    artifacts: list[TraceArtifact]
    results: dict[str, str] = {}  # requirement id -> worst outcome of its tests in the latest run


def test_results(artifacts: Iterable[Artifact]) -> dict[str, str]:
    """REQ id -> outcome from the latest test report (its 'verified' map), {} before the first run."""
    report = next((a for a in artifacts if a.kind is ArtifactKind.TEST_REPORT and not a.retired), None)
    return {str(k): str(v) for k, v in (report.content.get("verified") or {}).items()} if report else {}


def requirement_titles(artifacts: Iterable[Artifact]) -> dict[str, str]:
    titles: dict[str, str] = {}
    for a in artifacts:
        if a.kind is ArtifactKind.REQUIREMENTS and not a.retired:
            for item in a.content.get("requirements", []):
                if isinstance(item, dict) and item.get("id"):
                    titles[str(item["id"])] = str(item.get("title") or item["id"])
    return titles


def impact(artifacts: Iterable[Artifact], requirement_ids: Iterable[str]) -> dict[str, list[TraceArtifact]]:
    """Which artifacts a change to these requirements touches: every live artifact whose covers name one."""
    live = [a for a in artifacts if not a.retired and a.kind is not ArtifactKind.REQUIREMENTS]
    return {
        rid: [TraceArtifact(id=a.id, title=a.title, phase=a.phase.value, kind=a.kind.value, covers=list(a.covers)) for a in live if rid in a.covers]
        for rid in requirement_ids
    }


class RequirementStatus(BaseModel):
    """How far one requirement got: drawn in a diagram, implemented, tested, and the latest test outcome."""

    id: str
    title: str
    design: bool
    code: bool
    tests: bool
    result: str | None = None  # passed | failed | error | skipped, None if no test ran

    @property
    def verified(self) -> bool:
        return self.result == "passed"


def requirement_status(artifacts: list[Artifact]) -> list[RequirementStatus]:
    live = [a for a in artifacts if not a.retired]
    titles = requirement_titles(live)
    results = test_results(live)
    defined = [rid for a in live if a.kind is ArtifactKind.REQUIREMENTS for rid in a.defines]

    def has(rid: str, kind: ArtifactKind) -> bool:
        return any(a.kind is kind and rid in a.covers for a in live)

    return [
        RequirementStatus(
            id=rid,
            title=titles.get(rid, rid),
            design=has(rid, ArtifactKind.DIAGRAM),
            code=has(rid, ArtifactKind.SOURCE_FILE),
            tests=has(rid, ArtifactKind.TEST_FILE),
            result=results.get(rid),
        )
        for rid in defined
    ]


def trace_view(artifacts: list[Artifact]) -> TraceView:
    """The trace graph for display. Requirements artifacts list their items under content['requirements']
    (each with 'id' and 'title'); an id without a listed title is shown by its id."""
    live = [a for a in artifacts if not a.retired]
    titles = requirement_titles(live)
    defined = [rid for a in live if a.kind is ArtifactKind.REQUIREMENTS for rid in a.defines]
    return TraceView(
        report=requirement_coverage(live),
        requirements=[TraceNode(id=rid, title=titles.get(rid, rid)) for rid in defined],
        artifacts=[
            TraceArtifact(id=a.id, title=a.title, phase=a.phase.value, kind=a.kind.value, covers=list(a.covers))
            for a in live
            if a.kind is not ArtifactKind.REQUIREMENTS
        ],
        results=test_results(live),
    )
