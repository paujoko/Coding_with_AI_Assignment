import { fireEvent, render, screen } from "@testing-library/react";
import type { PhaseState } from "../api/types";
import { statusHint } from "../lib/status";
import { Wingspan } from "./Wingspan";

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
  }));
}

test("draws seven phases as left wing, body and right wing", () => {
  const { container } = render(<Wingspan phases={phases()} selected="design" onSelect={() => {}} />);
  expect(container.querySelectorAll(".wing-left .phase")).toHaveLength(3);
  expect(container.querySelectorAll(".wing-body .phase")).toHaveLength(1);
  expect(container.querySelectorAll(".wing-right .phase")).toHaveLength(3);
  expect(screen.getByText("codegen").closest(".wing-body")).not.toBeNull();
});

test("shows statuses, marks planned wings and the selected phase", () => {
  render(<Wingspan phases={phases()} selected="design" onSelect={() => {}} />);
  expect(screen.getByText("Approved")).toBeInTheDocument();
  expect(screen.getByText("Waiting for review")).toBeInTheDocument();
  expect(screen.getAllByText("Planned")).toHaveLength(5);
  expect(screen.getByRole("button", { name: /design/ })).toHaveAttribute("aria-current", "step");
});

test("selecting a phase reports its id", () => {
  const picked: string[] = [];
  render(<Wingspan phases={phases()} selected={null} onSelect={(id) => picked.push(id)} />);
  fireEvent.click(screen.getByRole("button", { name: /testing/ }));
  expect(picked).toEqual(["testing"]);
});

test("a locked phase names what to approve first", () => {
  const all = phases().map((p) => ({ ...p, implemented: true }));
  expect(statusHint(all[2], all)).toBe("Approve design first.");
});

test("a stale phase whose input is unapproved says to approve the input first", () => {
  const all = phases().map((p) => ({ ...p, implemented: true }));
  all[0] = { ...all[0], status: "draft", title: "Requirements" };
  all[1] = { ...all[1], status: "stale" };
  expect(statusHint(all[1], all)).toMatch(/^Requirements changed\. Approve it again/);
});
