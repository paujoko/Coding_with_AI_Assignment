# 0015 The developer's own folder, synced both ways, decided by code

- Date: 2026-11-14
- Status: accepted
- Decided by: Ben with Claude Code (Opus 5.5), session s04

## Context

Until now the generated files lived only in `workspaces/<project>/files/`, inside the Wings repository and ignored by git. A developer could change code only through the edit button in the Wings UI. Two problems for the grading:

- **C2 (alignment under change).** The brief asks Wings to detect when diagrams and code "have diverged, for example after the developer edited the code by hand, and offering to fix the inconsistency in one direction or the other". A hand edit in the developer's own editor was invisible to Wings.
- **C3 (usability).** Developers work in their editor, run the program from a terminal and commit to git. A folder hidden in the tool's repository fits none of that.

## Decision

1. **One folder per project, chosen by the developer.** At creation (start page, `POST /projects` with `folder`) or later (Folder view, `PUT /projects/{id}/folder`, `wings folder --set`, MCP `set_folder`). It must be an absolute path whose parent exists, empty or new, outside Wings' own folders, not a drive root or the home folder itself. Unlinking leaves the files where they are.
2. **Layout of a normal project.** What the workspace keeps under `app/` (code, tests, Dockerfile, start scripts) goes to the top of the folder; Wings' documents (requirements, diagrams, review, reports) go to `docs/wings/`.
3. **Wings to folder after every change.** After every action that saved artifacts, every edit in the UI and every import, the orchestrator writes the current files (`domain/sync.py: plan_export`). It never overwrites a file the developer changed or deleted by hand, and never restores a deleted one behind their back. A retired artifact's file is removed only if nobody changed it. A folder problem (unplugged drive, no rights) is logged as `folder.error` and never fails the action.
4. **Folder to Wings only when the developer says so.** The project keeps a manifest: per file, the artifact revision and a SHA-256 of the text Wings wrote (line endings normalized, so a Windows editor's `\r\n` is not a change). Anything that differs is a change (`folder_changes`): modified, deleted, or a new `.py`, `.html`, `.css`, `.js` file in the program part. The owning wing judges the content (`apply_developer_edit`, and the new `adopt_developer_file` for new files), so invalid Python is listed but not importable. Code, tests, deployment files and diagrams can be imported; requirements and computed reports cannot (they are restored instead). Importing turns the chosen changes into new revisions by the developer, all or nothing. Their phases go back to draft, their dependants become stale, and design versus code is compared again by code. When they disagree, the conversation of the changed phase gets the two repair directions as next steps, the same ones the consistency check in P7 offers: "Update the design from the code" and "Update the code from the design".
5. **Restore** writes Wings' version of a changed or deleted file back. New files the developer created are never deleted by Wings.
6. **Ports and adapters as everywhere else.** `ProjectFolder` port (`application/ports.py`), `LocalProjectFolder` adapter (`adapters/project_folder.py`, the only code that touches the developer's disk). The adapter refuses paths outside the folder, skips tool folders (`.git`, `.venv`, `node_modules`, caches), binary files and files over 1 MB. The rules are pure functions in the domain. Wings still never import each other.

Rejected:

- **Make the developer's folder the store** (`project.json`, revisions and logs inside their project). Simpler, but it puts Wings' bookkeeping into their repository, and a `git checkout` would rewrite Wings' history.
- **Import hand edits automatically, as soon as they appear.** It would make the change propagation of C2 happen without the developer deciding, and a half-saved file would become a revision. "The developer stays in control" is the brief's first rule for every phase.
- **A file watcher.** Needs a dependency and a background thread per project. The UI asks on window focus and every few seconds, and every API call recomputes the status, which is cheap for project-sized folders.
- **A folder picker in the page.** A browser does not give a page the absolute path of a chosen folder. Amended the same day on Ben's request: the backend runs on the developer's computer, so it opens the operating system's own dialog (`FolderPicker` port, Tkinter in a child process, `POST /system/pick-folder`). Typing or pasting the path still works, and is the fallback where no dialog can be shown.

## Consequences

- C2 can now be shown with a real editor: change a method in VS Code, switch back to Wings, import, see "Task.archive() is in the code but not in the class diagram", pick a direction. The same works for deleting a file and for editing a `.puml` diagram by hand.
- The folder is a normal project: `run.ps1`, `python -m pytest`, `git init` all work there.
- Two things are new for the project model: `Project.folder` (path, manifest, last sync). Old `project.json` files load unchanged (no folder). API version 8.
- Limits: a requirement change still goes through the Requirements step, not through `requirements.md`. JavaScript and HTML can be imported, but the drift check still only compares Python classes and public methods with the class diagram. Wings notices a change only when the UI asks (focus, every 8 s, after each step) or when the CLI or MCP asks, not the moment the file is saved.
