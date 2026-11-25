import { fireEvent, render, screen } from "@testing-library/react";
import type { PhaseState, Project } from "../api/types";
import { ProjectSwitcher } from "./ProjectSwitcher";

const phases: PhaseState[] = [
  { id: "requirements", title: "Requirements", status: "draft", requires: [], implemented: true, can_run: true, updated_at: "", stale_cause: null },
];

const project = (id: string, name: string, extra: Partial<Project> = {}): Project => ({ id, name, created_at: "", phases, ...extra });

function setup(projects: Project[]) {
  const onDelete = vi.fn();
  const onPick = vi.fn();
  render(<ProjectSwitcher projects={projects} current={projects[0]} creating={false} busy={false} onPick={onPick} onNew={() => {}} onDelete={onDelete} />);
  fireEvent.click(screen.getByRole("button", { name: /Snake/ }));
  return { onDelete, onPick };
}

test("a project is deleted only after a yes, and the message says the folder stays", () => {
  const { onDelete, onPick } = setup([project("snake", "Snake", { folder: { path: "C:/WingsProjects/snake", synced_at: null } }), project("chess", "Chess")]);

  fireEvent.click(screen.getByRole("button", { name: "Delete Snake" }));
  expect(onDelete).not.toHaveBeenCalled();
  expect(screen.getByRole("group", { name: "Delete Snake?" })).toHaveTextContent("The files in C:/WingsProjects/snake stay.");

  fireEvent.click(screen.getByRole("button", { name: "Delete project" }));
  expect(onDelete).toHaveBeenCalledWith("snake");
  expect(onPick).not.toHaveBeenCalled();
});

test("Cancel keeps the project", () => {
  const { onDelete } = setup([project("snake", "Snake"), project("chess", "Chess")]);

  fireEvent.click(screen.getByRole("button", { name: "Delete Chess" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(onDelete).not.toHaveBeenCalled();
  expect(screen.getByRole("menuitem", { name: /Chess/ })).toBeInTheDocument();
});

test("a project an agent works on cannot be deleted", () => {
  setup([project("snake", "Snake"), project("chess", "Chess", { running: { phase: "codegen", action: "generate", label: "Write the code", started_at: "" } })]);
  expect(screen.getByRole("button", { name: "Delete Chess" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Delete Snake" })).toBeEnabled();
});
