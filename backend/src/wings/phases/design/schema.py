"""Data shapes of the design wing. The diagram itself is a domain model shared with other wings."""

from pydantic import BaseModel, Field

from wings.domain.diagrams import DiagramItem, DiagramKind

__all__ = ["ArchitectOutput", "DiagramItem", "DiagramKind"]


class ArchitectOutput(BaseModel):
    notes: str = Field(description="Shown in the chat, at most two short sentences (about 40 words): the main design choice and the one open point. Do not list the diagrams")
    diagrams: list[DiagramItem] = Field(min_length=1)
