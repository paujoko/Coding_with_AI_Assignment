"""Data shapes of the refinement wing: review findings and the refined diagram set."""

from typing import Literal

from pydantic import BaseModel, Field

from wings.domain.diagrams import DiagramItem

Severity = Literal["high", "medium", "low"]


class Finding(BaseModel):
    id: str = Field("", description="Leave empty; ids F1, F2 ... are assigned by code")
    severity: Severity
    diagram: str = Field(description="Name of the diagram the finding is about, or 'all'")
    finding: str = Field(description="What is wrong or missing, in one or two sentences")
    suggestion: str = Field(description="What to change")
    source: Literal["reviewer", "check"] = "reviewer"
    status: Literal["open", "applied"] = "open"


class ReviewOutput(BaseModel):
    summary: str = Field(description="Shown in the chat, at most two short sentences (about 40 words): the overall judgement and the most important gap. Do not repeat the findings")
    findings: list[Finding] = Field(default_factory=list)


class RefinerOutput(BaseModel):
    notes: str = Field(description="Shown in the chat, at most two short sentences (about 40 words): what changed and the one thing left open. Do not describe the diagrams")
    diagrams: list[DiagramItem] = Field(min_length=1, description="The complete refined set, not only the changed diagrams")
