import { fireEvent, render, screen } from "@testing-library/react";
import type { PhaseState } from "../api/types";
import { statusHint } from "../lib/status";
import { StepList } from "./StepList";

const ids = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];

function phases(): PhaseState[] {
  return ids.map((id, i) => ({
    id,
    title: id,
    status: i === 0 ? "approved" : i === 1 ? "draft" : "locked",
    requires: i === 0 ? [] : [ids[i - 1]],
    implemented: i < 2,
    can_run: i < 2,
    updated_at: "",
    stale_cause: null,
  }));
}

test("groups the seven steps as specify (left wing), build (body) and verify and run (right wing)", () => {
  const { container } = render(<StepList phases={phases()} selected="design" onSelect={() => {}} />);
  expect(container.querySelectorAll('[data-wing="left"] .step')).toHaveLength(3);
  expect(container.querySelectorAll('[data-wing="body"] .step')).toHaveLength(1);
  expect(container.querySelectorAll('[data-wing="right"] .step')).toHaveLength(3);
  expect(screen.getByText("codegen").closest('[data-wing="body"]')).not.toBeNull();
});

test("only steps that wait for the developer show a word; done ones are ticked", () => {
  const { container } = render(<StepList phases={phases()} selected="design" onSelect={() => {}} />);
  expect(screen.getByText("Review")).toHaveClass("step-word");
  expect(screen.getByText("Done")).toHaveClass("sr-only"); // the tick says it, screen readers hear it
  expect(screen.getAllByText("Soon")).toHaveLength(5);
  expect(container.querySelector('[data-status="approved"] .step-icon svg')).not.toBeNull();
  expect(screen.getByRole("button", { name: /design/ })).toHaveAttribute("aria-current", "step");
});

test("selecting a step reports its id", () => {
  const picked: string[] = [];
  render(<StepList phases={phases()} selected={null} onSelect={(id) => picked.push(id)} />);
  fireEvent.click(screen.getByRole("button", { name: /testing/ }));
  expect(picked).toEqual(["testing"]);
});

test("a locked phase names what to approve first", () => {
  const all = phases().map((p) => ({ ...p, implemented: true }));
  expect(statusHint(all[2], all)).toBe("Approve design first.");
});

test("a stale phase names the phase that changed and what to approve first", () => {
  const all = phases().map((p) => ({ ...p, implemented: true }));
  all[0] = { ...all[0], status: "draft", title: "Requirements" };
  all[1] = { ...all[1], status: "stale", stale_cause: "requirements" };
  expect(statusHint(all[1], all)).toMatch(/^Requirements changed\. Approve Requirements again/);
});
