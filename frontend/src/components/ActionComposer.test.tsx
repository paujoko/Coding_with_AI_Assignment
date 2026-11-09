import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ActionInfo } from "../api/types";
import { ActionComposer, toInput } from "./ActionComposer";

const start: ActionInfo = {
  name: "start",
  label: "Start",
  description: "Describe the software.",
  input_schema: { properties: { description: { type: "string", description: "What should it do?" } }, required: ["description"] },
  message_field: "description",
};

test("converts form values to the types the schema asks for", () => {
  expect(toInput({ type: "integer" }, "42")).toBe(42);
  expect(toInput({ type: "number" }, "0.5")).toBe(0.5);
  expect(toInput({ type: "boolean" }, true)).toBe(true);
  expect(toInput({ type: "array" }, "a\n\n b ")).toEqual(["a", "b"]);
  expect(toInput({ type: "string" }, "   ")).toBeUndefined();
});

test("keeps the typed text when the action fails and clears it on success", async () => {
  let succeed = false;
  const onRun = vi.fn(async () => succeed);
  render(<ActionComposer actions={[start]} questions={[]} disabled={false} onRun={onRun} />);
  const box = screen.getByLabelText("What should it do?") as HTMLTextAreaElement;

  fireEvent.change(box, { target: { value: "A todo app" } });
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledWith("start", { description: "A todo app" }));
  expect(box.value).toBe("A todo app");

  succeed = true;
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  await waitFor(() => expect(box.value).toBe(""));
});

test("submit stays disabled until required fields are filled", () => {
  render(<ActionComposer actions={[start]} questions={[]} disabled={false} onRun={async () => true} />);
  expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
});
