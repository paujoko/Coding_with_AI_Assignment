"""Wings as an MCP server: AI clients (Claude Desktop, Claude Code, Cursor) drive the pipeline.

The same targeted control as the CLI and the HTTP API: list and create projects, run any action
of any wing, approve, reopen, read artifacts and the trace, and sync the project's folder. The deterministic UML checks the
architect uses are offered too, so a client can check its own PlantUML.

Run:  wings-mcp            (stdio transport; needs `pip install -e ".[mcp]"`)
Add to Claude Code:  claude mcp add wings -- <path to backend>/.venv/Scripts/wings-mcp
Gates still apply: a phase whose inputs are not approved answers with an error.
Real model calls happen only if the developer configured a paid provider (Settings or .env).
"""

import json
from typing import Any

from pydantic import ValidationError

from wings.application.orchestrator import ActionFailedError, Orchestrator
from wings.application.tools import consistency_report, plantuml_report
from wings.bootstrap import Container, build_container
from wings.domain.errors import DomainError
from wings.domain.project import Project

INSTRUCTIONS = (
    "Wings walks a software project through seven phases (requirements, design, refinement, codegen, testing, "
    "deployment, maintenance); each phase has LLM agents and waits for approval before the next one unlocks. "
    "Use list_phases to see the actions of each phase and their inputs, run_action to run one, approve when the "
    "developer accepts the result. Trace ids (REQ-001 ...) link requirements to diagrams."
)


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def _phases(project: Project) -> dict[str, str]:
    return {ph.value: st.status.value for ph, st in project.phases.items()}


def _safe(work) -> str:
    """Errors come back as a readable result instead of breaking the client's session."""
    try:
        return _dump(work())
    except (DomainError, ActionFailedError, ValidationError, ValueError) as err:
        return _dump({"error": str(err)})


def build_server(container: Container):
    from mcp.server.mcpserver import MCPServer  # optional dependency, only needed for this entry point

    orch: Orchestrator = container.orchestrator
    server = MCPServer("Wings", instructions=INSTRUCTIONS)

    @server.tool(description="The seven phases in pipeline order with their actions, input schemas and agents.")
    def list_phases() -> str:
        return _safe(lambda: [m.describe() for m in orch.registry.ordered()])

    @server.tool(description="All projects with the status of each phase.")
    def list_projects() -> str:
        return _safe(lambda: [{"id": p.id, "name": p.name, "phases": _phases(p)} for p in orch.list_projects()])

    @server.tool(description="Create a project. Returns its id. folder: optional absolute path of an empty or new folder for its files; without it the project gets a new folder under the projects directory (WINGS_PROJECTS_DIR, else ~/WingsProjects).")
    def create_project(name: str, folder: str | None = None) -> str:
        return _safe(lambda: (lambda p: {"id": p.id, "name": p.name, "phases": _phases(p)})(orch.create_project(name, folder=folder)))

    @server.tool(description="Status of every phase of a project.")
    def project_status(project: str) -> str:
        return _safe(lambda: {"id": project, "phases": _phases(orch.project(project))})

    @server.tool(
        description=(
            "Run an action of a phase, e.g. phase='requirements', action='start', input={'description': '...'}. "
            "See list_phases for the actions and their inputs. Returns the agent's reply and the new status."
        )
    )
    def run_action(project: str, phase: str, action: str, input: dict[str, Any] | None = None, attachments: list[str] | None = None) -> str:
        def work():
            result = orch.run_action(project, phase, action, input or {}, attachments=attachments or [])
            ph = orch.registry.get(phase).id
            return {
                "status": result.project.status(ph).value,
                "reply": result.outcome.reply,
                "saved": [f"{a.id} r{a.revision}" for a in result.outcome.artifacts],
                "stale": [s.value for s in result.stale],
                "data": result.outcome.data,
            }

        return _safe(work)

    @server.tool(description="Approve a phase (the developer accepts its result); the next phase unlocks.")
    def approve(project: str, phase: str) -> str:
        def work() -> dict[str, Any]:
            phases = _phases(orch.approve(project, phase))
            note = orch.approval_note(project, phase)  # e.g. how many requirements the tests verify (ADR 0020)
            return {"phases": phases} | ({"note": note} if note else {})

        return _safe(work)

    @server.tool(
        description=(
            "Change requests of a project, newest first: state (open, complete, dropped), progress per phase, "
            "the next step, and the receipt: which artifacts each change updated, added or removed."
        )
    )
    def list_changes(project: str) -> str:
        return _safe(lambda: [c.model_dump(mode="json") for c in orch.changes(project)])

    @server.tool(
        description=(
            "Carry change request `number` one phase further: runs that phase's update and, with approve=true, "
            "approves it when its checks pass. One phase per call; call again while stopped_reason is null and "
            "the change is open. Request a change first with run_action(phase='maintenance', action='change')."
        )
    )
    def advance_change(project: str, number: int, approve: bool = True) -> str:
        def work():
            result = orch.advance_change(project, number, approve=approve)
            return {
                "ran": [r.model_dump(mode="json") for r in result.ran],
                "approved": result.approved.value if result.approved else None,
                "stopped_reason": result.stopped_reason,
                "change": result.change.model_dump(mode="json"),
                "phases": _phases(result.project),
            }

        return _safe(work)

    @server.tool(
        description=(
            "Bring the first out-of-date (stale) phase up to date: runs that phase's update and, with approve=true, "
            "approves it when its checks pass. One phase per call; call again while stopped_reason is null and done is false."
        )
    )
    def catch_up(project: str, approve: bool = True) -> str:
        def work():
            result = orch.catch_up(project, approve=approve)
            return {
                "ran": [r.model_dump(mode="json") for r in result.ran],
                "approved": result.approved.value if result.approved else None,
                "stopped_reason": result.stopped_reason,
                "remaining": [p.value for p in result.remaining],
                "done": result.done,
                "phases": _phases(result.project),
            }

        return _safe(work)

    @server.tool(description="Reopen an approved phase for changes.")
    def reopen(project: str, phase: str) -> str:
        return _safe(lambda: {"phases": _phases(orch.reopen(project, phase))})

    @server.tool(description="The current artifacts of a phase (requirements, diagrams ...) with their text.")
    def get_artifacts(project: str, phase: str) -> str:
        def work():
            orch.project(project)
            ph = orch.registry.get(phase).id
            return [
                {"id": a.id, "title": a.title, "kind": a.kind.value, "revision": a.revision, "covers": a.covers, "text": a.text}
                for a in orch.store.list_artifacts(project, ph)
                if not a.retired
            ]

        return _safe(work)

    @server.tool(description="Traceability: which requirement appears in which artifact, which are uncovered, and the latest test outcome per requirement.")
    def get_trace(project: str) -> str:
        def work():
            view = orch.trace_view(project)
            return view.report.model_dump() | {"requirements": [r.model_dump() for r in view.requirements], "test_results": view.results}

        return _safe(work)

    @server.tool(
        description="The project's folder on the developer's computer: which files were changed, deleted or added by hand "
        "since Wings wrote them, and whether each can be imported."
    )
    def folder_status(project: str) -> str:
        return _safe(lambda: orch.folder_status(project).model_dump(mode="json"))

    @server.tool(description="Link the project to an empty or new folder (absolute path) and write its files there; an empty path unlinks.")
    def set_folder(project: str, path: str = "") -> str:
        return _safe(lambda: orch.set_folder(project, path or None).model_dump(mode="json"))

    @server.tool(
        description="Import hand edits from the folder as new revisions by the developer (all importable changes if paths is "
        "empty). Changed phases go back to draft, later ones become stale; design versus code is checked again."
    )
    def import_folder_changes(project: str, paths: list[str] | None = None) -> str:
        def work():
            r = orch.import_folder_changes(project, paths or None)
            return {"reply": r.reply, "imported": [c.path for c in r.imported], "stale": [s.value for s in r.stale], "drift": r.drift, "phases": _phases(r.project)}

        return _safe(work)

    @server.tool(description="Write Wings' version of these changed or deleted files back into the folder.")
    def restore_folder_files(project: str, paths: list[str]) -> str:
        return _safe(lambda: orch.restore_folder_files(project, paths).model_dump(mode="json"))

    @server.tool(description="Check a PlantUML diagram for syntax errors. Returns OK or the problems with line numbers.")
    def check_plantuml(source: str) -> str:
        return _safe(lambda: {"report": plantuml_report(source, orch.renderer)})

    @server.tool(
        description="Check that sequence diagrams agree with a class diagram (participants are classes, called operations exist)."
    )
    def check_consistency(class_diagram: str, sequence_diagrams: dict[str, str]) -> str:
        from wings.domain.uml import check_consistency as problems_of

        return _safe(
            lambda: {"report": consistency_report(class_diagram, sequence_diagrams), "problems": problems_of(class_diagram, sequence_diagrams)}
        )

    return server


def main() -> None:
    build_server(build_container()).run("stdio")


if __name__ == "__main__":
    main()
