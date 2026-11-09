"""Tools agents can call while they work. Deterministic and read-only: the LLM proposes, code verifies.

A wing chooses which tools an agent gets (`LLMAgent.ask(..., tools=[...])`). The same tools are
offered to external AI clients by the MCP server (`wings/mcp_server.py`).
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from wings.application.ports import ToolSpec
from wings.domain.phases import PhaseId
from wings.domain.code import compare_design_and_code
from wings.domain.trace import impact, requirement_titles, test_results
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


# --- Code checks ----------------------------------------------------------------


class PythonSource(BaseModel):
    path: str = Field(description="File path, e.g. todo/service.py")
    source: str = Field(description="The complete file content")


class CodeFiles(BaseModel):
    files: dict[str, str] = Field(description="Every generated file: path -> content")


def python_report(path: str, source: str) -> str:
    import ast

    try:
        ast.parse(source, filename=path)
    except SyntaxError as err:
        return f"Problems:\n- {path} line {err.lineno}: {err.msg}"
    return f"OK: {path} is valid Python."


def _design_class_diagram(ctx: "PhaseContext") -> str:
    classes = [a for a in ctx.current_design() if a.content.get("kind") == "class"]
    return classes[0].text or "" if classes else ""


def design_report(ctx: "PhaseContext", files: dict[str, str]) -> str:
    diagram = _design_class_diagram(ctx)
    if not diagram:
        return "There is no class diagram to compare with."
    drift = compare_design_and_code(diagram, files)
    return "OK: the code implements every class and operation of the class diagram, and nothing more." if drift.in_sync else "Problems:\n- " + "\n- ".join(drift.lines())


CHECK_PYTHON = AgentTool(
    name="check_python",
    description="Check that a Python file parses. Returns OK or the syntax error with its line.",
    input_model=PythonSource,
    run=lambda ctx, p: python_report(p.path, p.source),
)

COMPARE_WITH_DESIGN = AgentTool(
    name="compare_with_design",
    description=(
        "Compare your Python files with the class diagram of the approved design: classes and public methods "
        "missing in the code, and public ones the diagram does not show."
    ),
    input_model=CodeFiles,
    run=lambda ctx, p: design_report(ctx, p.files),
)

CODE_TOOLS = [CHECK_PYTHON, COMPARE_WITH_DESIGN]


# --- Trace queries ----------------------------------------------------------------


class RequirementIds(BaseModel):
    requirements: list[str] = Field(description="Requirement ids, e.g. ['REQ-002']")


def impact_report(ctx: "PhaseContext", payload: RequirementIds) -> str:
    artifacts = ctx.artifacts()
    titles = requirement_titles(artifacts)
    results = test_results(artifacts)
    lines = []
    for rid, touched in impact(artifacts, payload.requirements).items():
        if rid not in titles:
            lines.append(f"{rid}: no such requirement.")
            continue
        found = ", ".join(f"{a.title} ({a.phase})" for a in touched) or "nothing yet"
        lines.append(f"{rid} {titles[rid]}: {found}. Latest test: {results.get(rid, 'not run')}.")
    return "\n".join(lines) or "Name at least one requirement id."


TRACE_IMPACT = AgentTool(
    name="trace_impact",
    description=(
        "For requirement ids, list every diagram, source file and test file that traces to them, and their latest test "
        "outcome. Use it to see what a change touches."
    ),
    input_model=RequirementIds,
    run=impact_report,
)
