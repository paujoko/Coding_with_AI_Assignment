import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { Artifact } from "../api/types";
import { RunGuideView, runSequence } from "./RunGuideView";

const guide = (content: Record<string, unknown>): Artifact => ({
  id: "run-guide",
  kind: "run_guide",
  phase: "deployment",
  title: "Run guide",
  revision: 1,
  content: { start_command: "python -m todo", url: null, example_commands: [], stop_hint: "", checked: true, derived: false, ...content },
  text: "",
  path: "app/RUN.md",
  defines: [],
  covers: [],
  author: "system:deploy-check",
  retired: false,
  created_at: "2026-11-23T10:00:00Z",
});

const FOLDER = "C:\\Users\\dev\\Wings Projects\\todo";

function clipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return writeText;
}

test("the first line goes to the real project folder, quoted, then the start command; Copy all copies both", async () => {
  // Owner (s06): "it must describe exactly, with a copyable terminal command, how to start the application".
  const writeText = clipboard();
  render(<RunGuideView guide={guide({ example_commands: ['python -m todo add "Buy milk"', "python -m todo list"] })} folder={FOLDER} busy={false} onOpenFolder={() => {}} />);
  const lines = within(screen.getByRole("list", { name: "Commands to start the program" })).getAllByRole("listitem");
  expect(lines.map((l) => l.querySelector("code")?.textContent)).toEqual([`cd "${FOLDER}"`, "python -m todo"]);
  expect(screen.getByText("Checked by code")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /Copy all/ }));
  expect(writeText).toHaveBeenCalledWith(`cd "${FOLDER}"\npython -m todo`);
  expect(await screen.findByText("Copied")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: 'Copy: python -m todo add "Buy milk"' }));
  expect(writeText).toHaveBeenLastCalledWith('python -m todo add "Buy milk"');
  await waitFor(() => expect(screen.getAllByText("Copied")).toHaveLength(2));
});

test("a web app shows its address as a link in a new tab and says the program must run first", () => {
  render(<RunGuideView guide={guide({ start_command: "python -m shop", url: "http://127.0.0.1:8000/", stop_hint: "Ctrl+C", checked: false })} folder={FOLDER} busy={false} onOpenFolder={() => {}} />);
  const link = screen.getByRole("link", { name: /127\.0\.0\.1:8000/ });
  expect(link).toHaveAttribute("target", "_blank");
  expect(screen.getByText(/The program must be running first/)).toBeInTheDocument();
  expect(screen.getByText("To stop it: Ctrl+C")).toBeInTheDocument();
  expect(screen.queryByText("Checked by code")).not.toBeInTheDocument();
  expect(screen.getByText(/Not checked/)).toBeInTheDocument();
});

test("without a folder it says so and leads to the Folder view; without a start command it shows one honest line", () => {
  let opened = false;
  const { rerender } = render(<RunGuideView guide={guide({})} folder={null} busy={false} onOpenFolder={() => (opened = true)} />);
  expect(screen.getByText(/This project has no folder yet/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Copy all/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Choose a folder" }));
  expect(opened).toBe(true);

  rerender(<RunGuideView guide={guide({ start_command: "" })} folder={FOLDER} busy={false} onOpenFolder={() => {}} />);
  expect(screen.getByText(/No start command is known/)).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "Commands to start the program" })).not.toBeInTheDocument();
});

test("the sequence has one command per line and no cd without a folder", () => {
  expect(runSequence("/home/dev/todo", "python -m todo")).toBe('cd "/home/dev/todo"\npython -m todo');
  expect(runSequence(null, "python -m todo")).toBe("python -m todo");
});
