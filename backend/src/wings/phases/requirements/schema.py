"""Data shapes of the requirements wing: what the analyst agent returns and what the artifact stores."""

import re
from typing import Literal

from pydantic import BaseModel, Field

REQ_ID = re.compile(r"^REQ-(\d{3,})$")


class Question(BaseModel):
    id: str = Field(description="Q1, Q2, ...")
    question: str
    why: str = Field(description="Why the answer changes the requirements")
    options: list[str] = Field(default_factory=list, description="Optional suggested answers")


class RequirementItem(BaseModel):
    id: str = Field("", description="Keep the existing REQ-xxx id when revising; leave empty for a new requirement")
    title: str
    description: str
    type: Literal["functional", "non_functional"] = "functional"
    priority: Literal["must", "should", "could"] = "must"
    acceptance_criteria: list[str] = Field(default_factory=list, description="Testable, Given/When/Then style")


class AnalystOutput(BaseModel):
    """Either open questions (requirements empty) or a requirements set (questions empty)."""

    summary: str = Field(description="One paragraph: what the software is for")
    questions: list[Question] = Field(default_factory=list)
    requirements: list[RequirementItem] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, description="Everything decided without the developer saying so")


class RequirementsDoc(BaseModel):
    """Content of the `requirements` artifact; also what the developer edits."""

    summary: str
    requirements: list[RequirementItem]
    assumptions: list[str] = Field(default_factory=list)


def assign_ids(items: list[RequirementItem], keep: list[str], issued: list[str] | None = None) -> list[RequirementItem]:
    """Stable trace IDs.

    An item keeps its id only if that id is in `keep` (the requirements that exist now) and is not
    used twice. Every other item gets the next number after the highest id ever issued, so an id of
    a deleted requirement never comes back with a different meaning.
    """
    known = set(keep)
    used: set[str] = set()
    highest = max((int(m.group(1)) for rid in [*keep, *(issued or [])] if (m := REQ_ID.match(rid))), default=0)
    result = []
    for item in items:
        if item.id in known and item.id not in used:
            rid = item.id
        else:
            highest += 1
            rid = f"REQ-{highest:03d}"
        used.add(rid)
        result.append(item.model_copy(update={"id": rid}))
    return result


def render_markdown(doc: RequirementsDoc) -> str:
    lines = ["# Requirements", "", doc.summary, ""]
    for kind, heading in (("functional", "Functional requirements"), ("non_functional", "Non-functional requirements")):
        items = [r for r in doc.requirements if r.type == kind]
        if not items:
            continue
        lines += [f"## {heading}", ""]
        for r in items:
            lines += [f"### {r.id} {r.title} ({r.priority})", "", r.description, ""]
            lines += [f"- {c}" for c in r.acceptance_criteria]
            lines.append("")
    if doc.assumptions:
        lines += ["## Assumptions", ""] + [f"- {a}" for a in doc.assumptions] + [""]
    return "\n".join(lines).rstrip() + "\n"
