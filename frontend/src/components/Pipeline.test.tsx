import { fireEvent, render, screen } from "@testing-library/react";
import type { PhaseState } from "../api/types";
import { statusHint } from "../lib/status";
import { Pipeline } from "./Pipeline";

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

test("draws seven stations as left wing, body and right wing", () => {
  const { container } = render(<Pipeline phases={phases()} selected="design" onSelect={() => {}} />);
  expect(container.querySelectorAll('[data-wing="left"] .station')).toHaveLength(3);
  expect(container.querySelectorAll('[data-wing="body"] .station')).toHaveLength(1);
  expect(container.querySelectorAll('[data-wing="right"] .station')).toHaveLength(3);
  expect(screen.getByText("codegen").closest('[data-wing="body"]')).not.toBeNull();
});

test("each step says in one word what to do there, and marks the selected one", () => {
  render(<Pipeline phases={phases()} selected="design" onSelect={() => {}} />);
  expect(screen.getByText("Done")).toBeInTheDocument();
  expect(screen.getByText("Review")).toBeInTheDocument();
  expect(screen.getAllByText("Soon")).toHaveLength(5);
  expect(screen.getByText("3")).toBeInTheDocument(); // steps are numbered; approved ones show a check instead
  expect(screen.getByRole("button", { name: /design/ })).toHaveAttribute("aria-current", "step");
});

test("the track breaks where a later phase went out of date", () => {
  const all = phases();
  all[1] = { ...all[1], status: "stale", stale_cause: "requirements" };
  const { container } = render(<Pipeline phases={all} selected={null} onSelect={() => {}} />);
  const items = container.querySelectorAll(".pipeline-stations > li");
  expect(items[0]).toHaveAttribute("data-track", "broken");
  expect(items[6]).not.toHaveAttribute("data-track");
});

test("selecting a station reports its id", () => {
  const picked: string[] = [];
  render(<Pipeline phases={phases()} selected={null} onSelect={(id) => picked.push(id)} />);
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
