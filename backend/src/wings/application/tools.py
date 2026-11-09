"""Tools agents can call while they work. Deterministic and read-only: the LLM proposes, code verifies.

A wing chooses which tools an agent gets (`LLMAgent.ask(..., tools=[...])`). The same tools are
offered to external AI clients by the MCP server (`wings/mcp_server.py`).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from wings.application.ports import ToolSpec
from wings.domain.phases import PhaseId
from wings.domain.uml import basic_problems, check_consistency

if TYPE_CHECKING:
    from wings.application.phase import PhaseContext


class AgentTool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_model: type[BaseModel]
    run: Callable[[Any, Any], str]  # (PhaseContext, validated input) -> text the model reads

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=self.input_model.model_json_schema())


# --- UML checks ---------------------------------------------------------------


class PlantUMLSource(BaseModel):
    source: str = Field(description="A complete PlantUML diagram, from @startuml to @enduml")


class DesignSet(BaseModel):
    class_diagram: str = Field(description="PlantUML source of the class diagram")
    sequence_diagrams: dict[str, str] = Field(description="Sequence diagrams: title -> PlantUML source")


class Covers(BaseModel):
    covers: list[str] = Field(description="Every REQ id the planned diagrams cover, e.g. REQ-001")


def plantuml_report(source: str, renderer: Any) -> str:
    """Text for a person or a model: OK, or the problems with line numbers."""
    problems = basic_problems(source)
    if not problems and renderer is not None and renderer.available:
        error = renderer.check(source)
        if error:
            problems.append(error)
        elif error is None:
            return "OK: valid PlantUML."
    if problems:
        return "Problems:\n- " + "\n- ".join(problems)
    return "No basic problems found (full syntax check unavailable: no PlantUML renderer configured)."


def consistency_report(class_diagram: str, sequence_diagrams: dict[str, str]) -> str:
    problems = check_consistency(class_diagram, sequence_diagrams)
    return "OK: every participant is a class and every called operation exists." if not problems else "Problems:\n- " + "\n- ".join(problems)


def _coverage(ctx: "PhaseContext", payload: Covers) -> str:
    defined = [rid for a in ctx.artifacts(PhaseId.REQUIREMENTS) if not a.retired for rid in a.defines]
    uncovered = [r for r in defined if r not in payload.covers]
    unknown = sorted({c for c in payload.covers if c not in defined})
    if not uncovered and not unknown:
        return f"OK: all {len(defined)} requirements are covered."
    lines = []
    if uncovered:
        lines.append(f"Not covered by any diagram: {', '.join(uncovered)}.")
    if unknown:
        lines.append(f"These ids do not exist: {', '.join(unknown)}.")
    return "\n".join(lines)


CHECK_PLANTUML = AgentTool(
    name="check_plantuml",
    description="Check one PlantUML diagram for syntax errors before you return it. Returns OK or the problems with line numbers.",
    input_model=PlantUMLSource,
    run=lambda ctx, p: plantuml_report(p.source, ctx.renderer),
)

CHECK_CONSISTENCY = AgentTool(
    name="check_consistency",
    description=(
        "Check that the sequence diagrams agree with the class diagram: every participant is a class "
        "(actors excepted) and every called operation exists on the called class or its parents."
    ),
    input_model=DesignSet,
    run=lambda ctx, p: consistency_report(p.class_diagram, p.sequence_diagrams),
)

CHECK_COVERAGE = AgentTool(
    name="check_coverage",
    description="Check which approved requirements your planned diagrams do not cover yet, and which ids do not exist.",
    input_model=Covers,
    run=_coverage,
)

DESIGN_TOOLS = [CHECK_PLANTUML, CHECK_CONSISTENCY, CHECK_COVERAGE]
