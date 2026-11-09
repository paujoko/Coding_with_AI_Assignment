"""Data shapes of the design wing."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

DiagramKind = Literal["use_case", "class", "sequence", "activity", "component", "deployment", "state"]


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


class ArchitectOutput(BaseModel):
    notes: str = Field(description="Summary of the design for the developer, including open points")
    diagrams: list[DiagramItem] = Field(min_length=1)
