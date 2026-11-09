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


def trace_view(artifacts: list[Artifact]) -> TraceView:
    """The trace graph for display. Requirements artifacts list their items under content['requirements']
    (each with 'id' and 'title'); an id without a listed title is shown by its id."""
    live = [a for a in artifacts if not a.retired]
    titles: dict[str, str] = {}
    for a in live:
        if a.kind is ArtifactKind.REQUIREMENTS:
            for item in a.content.get("requirements", []):
                if isinstance(item, dict) and item.get("id"):
                    titles[str(item["id"])] = str(item.get("title") or item["id"])
    defined = [rid for a in live if a.kind is ArtifactKind.REQUIREMENTS for rid in a.defines]
    return TraceView(
        report=requirement_coverage(live),
        requirements=[TraceNode(id=rid, title=titles.get(rid, rid)) for rid in defined],
        artifacts=[
            TraceArtifact(id=a.id, title=a.title, phase=a.phase.value, kind=a.kind.value, covers=list(a.covers))
            for a in live
            if a.kind is not ArtifactKind.REQUIREMENTS
        ],
    )
