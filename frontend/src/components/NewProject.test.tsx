import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NewProject, nameFrom } from "./NewProject";

test("a project is named after the first clause of its description", () => {
  expect(nameFrom("A small to-do app for a team: tasks with a due date")).toBe("Small to-do app");
  expect(nameFrom("A command-line expense tracker that groups spending")).toBe("Command-line expense tracker");
  expect(nameFrom("  room booking. With calendars")).toBe("Room booking");
  expect(nameFrom("   ")).toBe("New project");
});

const describeIt = (text: string) => fireEvent.change(screen.getByLabelText("Describe the software"), { target: { value: text } });
const folderField = () => screen.getByLabelText("Project folder") as HTMLInputElement;
const start = () => fireEvent.click(screen.getByRole("button", { name: "Start" }));
// The backend's answer: a folder named after the project.
const suggest = () => vi.fn(async (name: string) => `C:\\Users\\me\\Wings\\${name.toLowerCase().replace(/\s+/g, "-")}`);

afterEach(() => vi.useRealTimers());

test("the folder is always shown and prefilled with the backend's default", async () => {
  const onSuggestFolder = suggest();
  render(<NewProject busy={false} onCreate={vi.fn(async () => true)} onSuggestFolder={onSuggestFolder} />);
  expect(folderField()).toBeVisible(); // no disclosure to open first
  await waitFor(() => expect(folderField().value).toBe("C:\\Users\\me\\Wings\\new-project"));
  expect(onSuggestFolder).toHaveBeenCalledWith("New project");
});

test("the suggestion follows the description after a pause, until the developer edits the folder", async () => {
  vi.useFakeTimers();
  const onSuggestFolder = suggest();
  render(<NewProject busy={false} onCreate={vi.fn(async () => true)} onSuggestFolder={onSuggestFolder} />);
  await act(() => vi.advanceTimersByTimeAsync(0));
  expect(folderField().value).toBe("C:\\Users\\me\\Wings\\new-project");

  describeIt("A room booking tool for a student association");
  expect(folderField().value).toBe("C:\\Users\\me\\Wings\\new-project"); // debounced: not on every key
  await act(() => vi.advanceTimersByTimeAsync(400));
  expect(folderField().value).toBe("C:\\Users\\me\\Wings\\room-booking-tool");

  fireEvent.change(folderField(), { target: { value: "D:\\work\\rooms" } });
  describeIt("A to-do app for a small team");
  await act(() => vi.advanceTimersByTimeAsync(400));
  expect(folderField().value).toBe("D:\\work\\rooms"); // their own choice is kept
});

test("a folder chosen with Browse is kept too", async () => {
  const onSuggestFolder = suggest();
  const onBrowse = vi.fn(async () => ({ path: "D:\\picked", empty: true, suggested: null }));
  render(<NewProject busy={false} onCreate={vi.fn(async () => true)} onSuggestFolder={onSuggestFolder} onBrowse={onBrowse} />);
  await waitFor(() => expect(folderField().value).not.toBe(""));
  fireEvent.click(screen.getByRole("button", { name: /Browse/ }));
  await waitFor(() => expect(folderField().value).toBe("D:\\picked"));
  const calls = onSuggestFolder.mock.calls.length;
  describeIt("A command-line expense tracker");
  await new Promise((r) => setTimeout(r, 450));
  expect(onSuggestFolder.mock.calls.length).toBe(calls);
  expect(folderField().value).toBe("D:\\picked");
});

test("without the endpoint the field stays empty and typing still works", async () => {
  const onCreate = vi.fn(async () => true);
  const onSuggestFolder = vi.fn(async () => {
    throw new Error("Not Found");
  });
  render(<NewProject busy={false} onCreate={onCreate} onSuggestFolder={onSuggestFolder} />);
  await waitFor(() => expect(onSuggestFolder).toHaveBeenCalled());
  expect(folderField().value).toBe("");
  describeIt("A to-do app for a small team");
  fireEvent.change(folderField(), { target: { value: "C:\\Projects\\todo" } });
  start();
  await waitFor(() => expect(onCreate).toHaveBeenCalledWith("To-do app", "A to-do app for a small team", [], "C:\\Projects\\todo"));
});

test("a project cannot start without a folder; the send button says what is missing", () => {
  const onCreate = vi.fn(async () => true);
  render(<NewProject busy={false} onCreate={onCreate} />);
  const send = screen.getByRole("button", { name: "Start" });
  expect(send).toHaveAttribute("title", "Describe the software first");
  describeIt("A to-do app for a small team");
  expect(send).toHaveAttribute("aria-disabled", "true");
  expect(send).toHaveAttribute("title", "Choose a project folder first");
  start();
  expect(onCreate).not.toHaveBeenCalled();
  expect(screen.getByRole("status")).toHaveTextContent("Choose a project folder to start.");
  expect(folderField()).toHaveFocus();
  // Enter in the description does not get around it either.
  fireEvent.keyDown(screen.getByLabelText("Describe the software"), { key: "Enter" });
  expect(onCreate).not.toHaveBeenCalled();
});

test("Enter starts the project with its folder", async () => {
  const onCreate = vi.fn(async () => true);
  render(<NewProject busy={false} onCreate={onCreate} onSuggestFolder={suggest()} />);
  describeIt("A to-do app for a small team");
  await waitFor(() => expect(folderField().value).toBe("C:\\Users\\me\\Wings\\to-do-app"));
  const send = screen.getByRole("button", { name: "Start" });
  expect(send).toHaveAttribute("aria-disabled", "false");
  fireEvent.keyDown(screen.getByLabelText("Describe the software"), { key: "Enter" });
  await waitFor(() => expect(onCreate).toHaveBeenCalledWith("To-do app", "A to-do app for a small team", [], "C:\\Users\\me\\Wings\\to-do-app"));
});
