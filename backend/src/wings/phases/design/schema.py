"""Data shapes of the design wing. The diagram itself is a domain model shared with other wings."""

from pydantic import BaseModel, Field

from wings.domain.diagrams import DiagramItem, DiagramKind

__all__ = ["ArchitectOutput", "DiagramItem", "DiagramKind"]


class ArchitectOutput(BaseModel):
    notes: str = Field(description="Summary of the design for the developer, including open points")
    diagrams: list[DiagramItem] = Field(min_length=1)
