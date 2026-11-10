import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import type { ActionInfo } from "../api/types";
import { Composer, toInput, type Values } from "./Composer";

const start: ActionInfo = {
  name: "start",
  label: "Start",
  description: "Describe the software.",
  input_schema: { properties: { description: { type: "string", description: "What should it do?" } }, required: ["description"] },
  message_field: "description",
};

function Harness({ onRun }: { onRun: (a: string, i: Record<string, unknown>) => Promise<boolean> }) {
  const [values, setValues] = useState<Values>({});
  const restore = (back: Values) => setValues((cur) => ({ ...back, ...Object.fromEntries(Object.entries(cur).filter(([, v]) => v !== "")) }));
  return <Composer actions={[start]} active="start" onActive={() => {}} values={values} onValues={setValues} onRestore={restore} disabled={false} onRun={onRun} />;
}

test("converts form values to the types the schema asks for", () => {
  expect(toInput({ type: "integer" }, "42")).toBe(42);
  expect(toInput({ type: "number" }, "0.5")).toBe(0.5);
  expect(toInput({ type: "boolean" }, true)).toBe(true);
  expect(toInput({ type: "array" }, "a\n\n b ")).toEqual(["a", "b"]);
  expect(toInput({ type: "string" }, "   ")).toBeUndefined();
});

test("the text leaves the box at once and comes back when the action fails", async () => {
  // Real run (s03): the text stayed in the box for minutes while the agent worked, which invited a second send.
  let finish: (ok: boolean) => void = () => {};
  const onRun = vi.fn(() => new Promise<boolean>((resolve) => (finish = resolve)));
  render(<Harness onRun={onRun} />);
  const box = screen.getByLabelText("What should it do?") as HTMLTextAreaElement;

  fireEvent.change(box, { target: { value: "A todo app" } });
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledWith("start", { description: "A todo app" }, []));
  expect(box.value).toBe(""); // gone while the agent works
  await act(async () => finish(false));
  expect(box.value).toBe("A todo app"); // refused: the text is back

  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  await act(async () => finish(true));
  expect(box.value).toBe("");
});

test("submit stays disabled until required fields are filled", () => {
  render(<Harness onRun={async () => true} />);
  expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
});

test("attached documents travel with the message and block sending while they upload", async () => {
  const onRun = vi.fn(async () => true);
  const ready = { key: "a", name: "brief.pdf", size: 10, status: "ready" as const, attachment: { id: "att-001", name: "brief.pdf", media_type: "", size: 10, chars: 5, created_at: "" } };
  const uploading = { key: "b", name: "spec.md", size: 5, status: "uploading" as const };
  const values = { "start.description": "A booking tool" };
  const props = { actions: [start], active: "start", onActive: () => {}, values, onValues: () => {}, disabled: false, onRun, onAddFiles: () => {}, onRemoveFile: () => {} };

  const { rerender } = render(<Composer {...props} files={[ready, uploading]} />);
  expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Attach documents" })).toBeInTheDocument();
  expect(screen.getByText("brief.pdf")).toBeInTheDocument();

  rerender(<Composer {...props} files={[ready]} />);
  fireEvent.click(screen.getByRole("button", { name: "Start" }));
  await waitFor(() => expect(onRun).toHaveBeenCalledWith("start", { description: "A booking tool" }, ["att-001"]));
});
