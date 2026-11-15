"""Command line: drive any wing directly, without the UI.

    wings phases                                   list wings and their actions
    wings create "Todo App" [--folder C:\\Projects\\todo]   new project, files also in that folder
    wings status todo-app                          phase statuses
    wings run todo-app requirements start description="A todo app"
    wings run todo-app design generate --json '{"guidance": "keep it small"}'
    wings approve todo-app requirements
    wings events todo-app [--after N]
    wings folder todo-app                          hand edits in the project's folder
    wings folder todo-app --set C:\\Projects\\todo   link a folder (empty or new) and write the files there
    wings folder todo-app --import [PATH ...]      take hand edits over as new revisions (all if no path)
    wings folder todo-app --restore PATH ...       put Wings' version of these files back
    wings folder todo-app --unlink
    wings serve [--port 8810]
"""

import argparse
import mimetypes
import json
import sys
from pathlib import Path

from wings.application.orchestrator import ActionFailedError
from wings.bootstrap import build_container
from wings.domain.errors import DomainError

ICONS = {"locked": "  .", "ready": "  >", "needs_input": "  ?", "draft": "  ~", "approved": "  +", "stale": "  !"}


def _status(project, registry) -> str:
    rows = [f"{project.name} ({project.id})"]
    for module in registry.ordered():
        st = project.status(module.id).value
        planned = "" if module.implemented else "  [planned]"
        rows.append(f"{ICONS[st]} {module.id.value:<12} {st}{planned}")
    return "\n".join(rows)


def _folder(status) -> str:
    if status.path is None:
        return "No folder linked. Use: wings folder <project> --set <absolute path>"
    rows = [f"Folder: {status.path}"]
    if status.problem:
        rows.append(f"  problem: {status.problem}")
    for c in status.changes:
        mark = "import" if c.importable else "      "
        rows.append(f"  {c.change:<9} {mark} {c.path}  {c.note}")
    if not status.changes and not status.problem:
        rows.append("  in sync with Wings")
    return "\n".join(rows)


def _payload(pairs: list[str], raw: str | None) -> dict:
    data = json.loads(raw) if raw else {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"Expected key=value, got '{pair}'.")
        data[key] = value
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wings", description="Targeted control of the Wings phases.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("phases")
    sub.add_parser("projects")
    create = sub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--folder", help="absolute path of an empty or new folder for the project's files")
    sub.add_parser("status").add_argument("project")
    run = sub.add_parser("run")
    run.add_argument("project")
    run.add_argument("phase")
    run.add_argument("action")
    run.add_argument("pairs", nargs="*", help="input as key=value")
    run.add_argument("--json", dest="raw", help="input as a JSON object")
    run.add_argument("--attach", action="append", default=[], metavar="ID", help="attached document id (repeatable)")
    att = sub.add_parser("attach", help="upload a document (text, Markdown, PDF, .docx) to a project")
    att.add_argument("project")
    att.add_argument("file")
    for name in ("approve", "reopen"):
        p = sub.add_parser(name)
        p.add_argument("project")
        p.add_argument("phase")
    ev = sub.add_parser("events")
    ev.add_argument("project")
    ev.add_argument("--after", type=int, default=0)
    fold = sub.add_parser("folder", help="the project's folder on this computer (ADR 0015)")
    fold.add_argument("project")
    how = fold.add_mutually_exclusive_group()
    how.add_argument("--set", metavar="PATH")
    how.add_argument("--unlink", action="store_true")
    how.add_argument("--import", dest="take", nargs="*", metavar="PATH")
    how.add_argument("--restore", nargs="+", metavar="PATH")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8810)
    args = parser.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("wings.main:app", port=args.port)
        return 0

    try:
        return _dispatch(args)
    except (DomainError, ActionFailedError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    orch = build_container().orchestrator
    reg = orch.registry
    if args.cmd == "phases":
        for m in reg.ordered():
            acts = ", ".join(a.name for a in m.actions) or "planned"
            print(f"{m.id.value:<12} {m.title:<20} actions: {acts}")
    elif args.cmd == "projects":
        for p in orch.list_projects():
            print(f"{p.id:<24} {p.name}")
    elif args.cmd == "create":
        print(_status(orch.create_project(args.name, folder=args.folder), reg))
    elif args.cmd == "status":
        print(_status(orch.project(args.project), reg))
    elif args.cmd == "run":
        result = orch.run_action(args.project, args.phase, args.action, _payload(args.pairs, args.raw), attachments=args.attach)
        if result.outcome.reply:
            print(result.outcome.reply, end="\n\n")
        for a in result.outcome.artifacts:
            print(f"saved {a.id} r{a.revision} -> {a.path}")
        print(_status(result.project, reg))
    elif args.cmd == "attach":
        path = Path(args.file)
        a = orch.add_attachment(args.project, path.name, mimetypes.guess_type(path.name)[0] or "", path.read_bytes())
        print(f"{a.id}  {a.name}  {len(a.text):,} characters of text  (use: wings run ... --attach {a.id})")
    elif args.cmd in ("approve", "reopen"):
        print(_status(getattr(orch, args.cmd)(args.project, args.phase), reg))
    elif args.cmd == "folder":
        if args.set:
            status = orch.set_folder(args.project, args.set)
        elif args.unlink:
            status = orch.set_folder(args.project, None)
        elif args.take is not None:
            result = orch.import_folder_changes(args.project, args.take or None)
            print(result.reply)
            status = orch.folder_status(args.project)
        elif args.restore:
            status = orch.restore_folder_files(args.project, args.restore)
        else:
            status = orch.folder_status(args.project)
        print(_folder(status))
    elif args.cmd == "events":
        for e in orch.store.list_events(args.project, args.after):
            print(f"{e.seq:>4} {e.at:%H:%M:%S} {e.kind:<16} {e.summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
