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


def _norm(title: str) -> str:
    return " ".join(title.lower().split())


def assign_ids(
    items: list[RequirementItem],
    keep: list[str],
    issued: list[str] | None = None,
    previous: list[RequirementItem] | None = None,
) -> list[RequirementItem]:
    """Stable trace IDs, assigned by code, never trusted from the model alone.

    1. An item keeps its id if that id is in `keep` (the requirements that exist now) and is not used twice.
    2. An item without such an id gets the id of a kept `previous` requirement with the same title
       (case and spacing ignored, repeated titles in their previous order), so a model that drops the ids
       while revising does not renumber everything. An explicit id whose title became the title of another
       kept requirement is treated as that requirement, so an id never moves to a different requirement.
    3. Every other item gets the next number after the highest id ever issued, so an id of a deleted
       requirement never comes back with a different meaning.
    """
    known = set(keep)
    kept_previous = [r for r in (previous or []) if r.id in known]
    title_of = {r.id: _norm(r.title) for r in kept_previous}
    by_title: dict[str, list[str]] = {}  # title -> ids in their previous order (titles can repeat)
    for r in kept_previous:
        by_title.setdefault(_norm(r.title), []).append(r.id)

    used: set[str] = set()
    ids: list[str | None] = []
    for item in items:  # explicit ids first, so a title match cannot take an id another item names
        title = _norm(item.title)
        # An id whose title changed into the title of another kept requirement is that other one, moved.
        moved = item.id in title_of and title_of[item.id] != title and any(i != item.id for i in by_title.get(title, []))
        if item.id in known and item.id not in used and not moved:
            used.add(item.id)
            ids.append(item.id)
        else:
            ids.append(None)
    for i, item in enumerate(items):
        if ids[i] is None:
            match = next((rid for rid in by_title.get(_norm(item.title), []) if rid not in used), None)
            if match:
                used.add(match)
                ids[i] = match
    highest = max((int(m.group(1)) for rid in [*keep, *(issued or [])] if (m := REQ_ID.match(rid))), default=0)
    result = []
    for item, rid in zip(items, ids, strict=True):
        if rid is None:
            highest += 1
            rid = f"REQ-{highest:03d}"
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
