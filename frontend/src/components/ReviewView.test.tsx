import { fireEvent, render, screen } from "@testing-library/react";
import type { Artifact } from "../api/types";
import { ReviewView } from "./ReviewView";

const finding = (id: string, severity: string, status = "open") => ({
  id,
  severity,
  diagram: "Domain classes",
  finding: `Problem ${id}`,
  suggestion: `Fix ${id}`,
  source: "reviewer",
  status,
});

const review: Artifact = {
  id: "review",
  kind: "review",
  phase: "refinement",
  title: "Design review",
  revision: 2,
  content: { summary: "Mostly fine.", findings: [finding("F1", "high"), finding("F2", "low"), finding("F3", "medium", "applied")] },
  text: "",
  path: "refinement/review.md",
  defines: [],
  covers: [],
  author: "agent:reviewer",
  retired: false,
  created_at: "2026-11-09T10:00:00Z",
};

test("open findings above low severity are picked; the developer changes the pick and applies it", () => {
  const applied: string[][] = [];
  render(<ReviewView review={review} canRun busy={false} onApply={(ids) => applied.push(ids)} />);
  expect(screen.getByRole("checkbox", { name: "Apply F1" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Apply F2" })).not.toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Apply F3" })).toBeDisabled(); // already applied
  fireEvent.click(screen.getByRole("checkbox", { name: "Apply F2" }));
  fireEvent.click(screen.getByRole("button", { name: /Apply 2 findings/ }));
  expect(applied).toEqual([["F1", "F2"]]);
});

test("without a pick there is nothing to apply", () => {
  render(<ReviewView review={review} canRun busy={false} onApply={() => {}} />);
  fireEvent.click(screen.getByRole("checkbox", { name: "Apply F1" }));
  expect(screen.getByRole("button", { name: /Pick findings to apply/ })).toBeDisabled();
});
