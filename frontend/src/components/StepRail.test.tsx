import { fireEvent, render, screen, within } from "@testing-library/react";
import type { PhaseState, PhaseStatus } from "../api/types";
import { StepRail } from "./StepRail";

const IDS = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];

function phases(statuses: Partial<Record<string, PhaseStatus>>): PhaseState[] {
  return IDS.map((id, i) => ({
    id,
    title: id,
    status: statuses[id] ?? "locked",
    requires: i === 0 ? [] : [IDS[i - 1]],
    implemented: true,
    can_run: true,
    updated_at: "",
    stale_cause: null,
  }));
}

test("the steps read in plain words, with Your program below the line", () => {
  render(<StepRail phases={phases({ requirements: "approved", design: "draft" })} redo={[]} running={null} selected="design" onSelect={() => {}} />);
  const steps = within(screen.getByRole("navigation", { name: "Steps" })).getAllByRole("button");
  expect(steps.map((b) => b.querySelector(".rail-title")?.textContent)).toEqual(["Requirements", "Design", "Design review", "Code", "Tests", "Deployment", "Your program"]);
  expect(screen.getByRole("button", { name: /Design Your turn/ })).toHaveAttribute("aria-current", "step");
});

test("only the step that waits says a word; steps that have to follow a change say Redo", () => {
  render(<StepRail phases={phases({ requirements: "approved", design: "draft", refinement: "stale" })} redo={["refinement"]} running={null} selected={null} onSelect={() => {}} />);
  expect(screen.getByText("Your turn")).toHaveClass("rail-word");
  expect(screen.getByText("Redo")).toHaveClass("rail-word");
  expect(screen.getByText("Accepted")).toHaveClass("sr-only");
});

test("the step an agent works on says Working, and clicks open steps", () => {
  const picked: string[] = [];
  render(<StepRail phases={phases({ requirements: "approved", design: "ready" })} redo={[]} running="design" selected={null} onSelect={(id) => picked.push(id)} />);
  expect(screen.getByText("Working")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Requirements/ }));
  expect(picked).toEqual(["requirements"]);
});
