import { fireEvent, render, screen } from "@testing-library/react";
import type { Artifact } from "../api/types";
import { FilesView } from "./FilesView";

const file = (path: string, text: string): Artifact => ({
  id: `source-${path}`,
  kind: "source_file",
  phase: "codegen",
  title: path,
  revision: 1,
  content: { path, purpose: `Purpose of ${path}` },
  text,
  path: `app/${path}`,
  defines: [],
  covers: ["REQ-001"],
  author: "agent:coder",
  retired: false,
  created_at: "2026-11-09T10:00:00Z",
});

test("the first file by path is open; another opens on click and can be edited into a new revision", async () => {
  const saved: string[] = [];
  render(
    <FilesView
      title="Code"
      summary=""
      files={[file("todo/service.py", "class TaskService:\n    pass"), file("todo/cli.py", "class Cli:\n    pass")]}
      focus={null}
      busy={false}
      editable
      onOpenRequirement={() => {}}
      onSave={async (id, text) => {
        saved.push(`${id}: ${text}`);
      }}
    />,
  );
  expect(screen.getByLabelText("Contents of todo/cli.py")).toHaveTextContent("class Cli:");
  fireEvent.click(screen.getByRole("button", { name: /todo\/service.py/ }));
  expect(screen.getByLabelText("Contents of todo/service.py")).toHaveTextContent("class TaskService:");
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  fireEvent.change(screen.getByLabelText("Edit todo/service.py"), { target: { value: "class TaskService: ..." } });
  fireEvent.click(screen.getByRole("button", { name: "Save as revision 2" }));
  await screen.findByRole("button", { name: "Edit" });
  expect(saved).toEqual(["source-todo/service.py: class TaskService: ..."]);
});
