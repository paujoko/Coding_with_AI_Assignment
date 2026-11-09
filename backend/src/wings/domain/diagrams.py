"""UML diagrams as data: shared by every wing that writes or reads diagrams (design, refinement, later ones).

A diagram is PlantUML source plus its kind, the REQ ids it covers and why it looks like this.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

DiagramKind = Literal["use_case", "class", "sequence", "activity", "component", "deployment", "state"]

# Reading order: goals, structure, behaviour, runtime.
DIAGRAM_ORDER: list[str] = ["use_case", "class", "sequence", "activity", "state", "component", "deployment"]


class DiagramItem(BaseModel):
    name: str = Field(description="Short, unique, e.g. 'Use cases' or 'Domain classes'")
    kind: DiagramKind
    plantuml: str = Field(description="Complete PlantUML source from @startuml to @enduml")
    covers: list[str] = Field(default_factory=list, description="REQ ids this diagram addresses")
    rationale: str = Field(description="Why the diagram looks like this; the main design choices")

    @field_validator("plantuml")
    @classmethod
    def _is_plantuml(cls, src: str) -> str:
        src = src.strip()
        if not src.startswith("@startuml") or not src.rstrip().endswith("@enduml"):
            raise ValueError("plantuml must start with @startuml and end with @enduml")
        return src + "\n"


def _slug(name: str) -> str:
    from wings.domain.project import slugify

    return slugify(name)


def unique_slugs(diagrams: list[DiagramItem]) -> list[str]:
    """One id per diagram even if names collide ("Use cases" / "Use-Cases") or have no Latin letters."""
    seen: set[str] = set()
    result = []
    for d in diagrams:
        base = _slug(d.name)
        if base == "project" and "project" not in d.name.lower():  # slugify's fallback for names like "类图"
            base = d.kind.replace("_", "-")
        slug, n = base, 1
        while slug in seen:
            n += 1
            slug = f"{base}-{n}"
        seen.add(slug)
        result.append(slug)
    return result


def describe_set(diagrams: list[tuple[str, str, str]]) -> str:
    """(kind, title, source) triples as one text block for a prompt."""
    return "\n\n".join(f"[{kind}] {title}:\n{source}" for kind, title, source in diagrams) or "(no diagrams)"

