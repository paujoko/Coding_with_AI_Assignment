import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { DESIGN_GENERATE } from "../lib/choices.fixture";
import { StartChoices } from "./StartChoices";

test("ticks the defaults, keeps the schema's order and switches the level", () => {
  const onChange = vi.fn();
  render(<StartChoices action={DESIGN_GENERATE} values={{ kinds: ["use_case", "class"], level: "simple" }} onChange={onChange} disabled={false} />);
  expect(screen.getByRole("group", { name: "Diagrams to draw" })).toBeTruthy();
  expect((screen.getByRole("checkbox", { name: /^Use case/ }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole("checkbox", { name: /^Sequence/ }) as HTMLInputElement).checked).toBe(false);
  expect(screen.getByText("The parts of the program; the code is checked against it")).toBeTruthy();

  fireEvent.click(screen.getByRole("checkbox", { name: /^Sequence/ }));
  expect(onChange).toHaveBeenLastCalledWith({ kinds: ["use_case", "class", "sequence"], level: "simple" });
  fireEvent.click(screen.getByRole("checkbox", { name: /^Use case/ }));
  expect(onChange).toHaveBeenLastCalledWith({ kinds: ["class"], level: "simple" });
  fireEvent.click(screen.getByRole("radio", { name: /^Detailed/ }));
  expect(onChange).toHaveBeenLastCalledWith({ kinds: ["use_case", "class"], level: "detailed" });
});

test("cannot be changed while the agent works", () => {
  render(<StartChoices action={DESIGN_GENERATE} values={{ kinds: [], level: "simple" }} onChange={() => {}} disabled />);
  expect((screen.getByRole("group", { name: "How detailed" }) as HTMLFieldSetElement).disabled).toBe(true);
});
