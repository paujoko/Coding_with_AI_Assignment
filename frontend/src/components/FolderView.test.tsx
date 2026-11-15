import { fireEvent, render, screen } from "@testing-library/react";
import type { FolderChange, FolderStatus, PhaseState } from "../api/types";
import { FolderView } from "./FolderView";

const phases = [
  { id: "codegen", title: "Code generation" },
  { id: "testing", title: "Testing" },
  { id: "requirements", title: "Requirements" },
] as PhaseState[];

const change = (path: string, extra: Partial<FolderChange> = {}): FolderChange => ({
  path,
  change: "modified",
  artifact_id: "a",
  phase: "codegen",
  importable: true,
  newer_in_wings: false,
  note: "Changed in the folder.",
  ...extra,
});

const props = (status: FolderStatus | null) => ({
  status,
  phases,
  busy: false,
  result: null,
  onLink: vi.fn(async () => true),
  onUnlink: vi.fn(),
  onImport: vi.fn(),
  onRestore: vi.fn(),
  onRefresh: vi.fn(),
  onOpenPhase: vi.fn(),
});

test("without a folder it asks for one", () => {
  const p = props({ path: null, exists: true, changes: [], problem: null });
  render(<FolderView {...p} />);
  fireEvent.change(screen.getByLabelText(/Folder on this computer/), { target: { value: "C:\\Projects\\todo" } });
  fireEvent.click(screen.getByRole("button", { name: "Use this folder" }));
  expect(p.onLink).toHaveBeenCalledWith("C:\\Projects\\todo");
});

test("in sync says so", () => {
  render(<FolderView {...props({ path: "C:\\Projects\\todo", exists: true, changes: [], problem: null })} />);
  expect(screen.getByText(/In sync/)).toBeInTheDocument();
  expect(screen.getByText("C:\\Projects\\todo")).toBeInTheDocument();
});

test("hand edits are listed; only importable ones can be picked and imported", () => {
  const p = props({
    path: "/home/me/todo",
    exists: true,
    problem: null,
    changes: [
      change("todo/models.py"),
      change("tests/test_export.py", { change: "added", phase: "testing", artifact_id: null }),
      change("docs/wings/requirements.md", { importable: false, phase: "requirements", note: "Requirements are edited in Wings." }),
    ],
  });
  render(<FolderView {...p} />);
  expect(screen.getByLabelText("Import docs/wings/requirements.md")).toBeDisabled();
  fireEvent.click(screen.getByLabelText("Import todo/models.py")); // unpick one of the two picked by default
  fireEvent.click(screen.getByRole("button", { name: "Import 1 into Wings" }));
  expect(p.onImport).toHaveBeenCalledWith(["tests/test_export.py"]);
  // A new file has no Wings version to restore; the other two do.
  expect(screen.getAllByRole("button", { name: /Restore Wings' version/ })).toHaveLength(2);
  fireEvent.click(screen.getAllByRole("button", { name: /Restore Wings' version/ })[0]);
  expect(p.onRestore).toHaveBeenCalledWith(["todo/models.py"]);
});

test("an edit Wings has replaced since is flagged", () => {
  render(<FolderView {...props({ path: "/x", exists: true, problem: null, changes: [change("todo/models.py", { newer_in_wings: true })] })} />);
  expect(screen.getByText(/Wings has a newer version/)).toBeInTheDocument();
});

test("a missing folder is explained", () => {
  render(<FolderView {...props({ path: "/x", exists: false, problem: "The folder /x is not there.", changes: [] })} />);
  expect(screen.getByRole("alert")).toHaveTextContent("not there");
  expect(screen.queryByText(/In sync/)).not.toBeInTheDocument();
});

test("Browse opens the folder dialog and puts the chosen path in the field", async () => {
  const p = props({ path: null, exists: true, changes: [], problem: null });
  const onBrowse = vi.fn(async () => ({ path: "C:\\Projects", empty: false, suggested: "C:\\Projects\\to-do-app" }));
  render(<FolderView {...p} onBrowse={onBrowse} />);
  fireEvent.click(screen.getByRole("button", { name: /Browse/ }));
  expect(await screen.findByDisplayValue("C:\\Projects\\to-do-app")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("already has files");
  fireEvent.click(screen.getByRole("button", { name: "Use this folder" }));
  expect(p.onLink).toHaveBeenCalledWith("C:\\Projects\\to-do-app");
});

test("without a folder dialog there is no Browse button; typing still works", () => {
  render(<FolderView {...props({ path: null, exists: true, changes: [], problem: null })} />);
  expect(screen.queryByRole("button", { name: /Browse/ })).toBeNull();
  expect(screen.getByLabelText("Folder on this computer")).toBeInTheDocument();
});
