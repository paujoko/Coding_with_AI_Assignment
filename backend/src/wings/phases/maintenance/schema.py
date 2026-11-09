"""Data shapes of the maintenance wing."""

from typing import Literal

from pydantic import BaseModel, Field

ChangeKind = Literal["bug", "change", "new_requirement"]


class ImpactOutput(BaseModel):
    """The impact analyst's reading of a change request. Code checks the ids and computes what they touch."""

    kind: ChangeKind = Field(description="bug: the code does not do what a requirement says; change: a requirement changes; new_requirement: something new")
    summary: str = Field(description="One sentence: what the developer wants")
    affected: list[str] = Field(default_factory=list, description="Existing REQ ids the change touches")
    requirements_update: str = Field(
        "", description="For change and new_requirement: the instruction for the requirements analyst. Empty for a bug."
    )
    fix: str = Field("", description="For a bug: what is wrong in the code and how to fix it. Empty otherwise.")
    steps: list[str] = Field(default_factory=list, description="The plan, one short line per phase that has to move")
