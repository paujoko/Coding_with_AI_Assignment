import type { PhaseState, PhaseStatus } from "../api/types";

export const STATUS_LABEL: Record<PhaseStatus, string> = {
  locked: "Locked",
  ready: "Ready",
  needs_input: "Needs your answer",
  draft: "Waiting for review",
  approved: "Approved",
  stale: "Out of date",
};

export function statusHint(phase: PhaseState, all: PhaseState[]): string {
  if (!phase.implemented) return "Planned. This wing is not built yet.";
  const missing = phase.requires
    .filter((r) => all.find((p) => p.id === r)?.status !== "approved")
    .map((r) => all.find((p) => p.id === r)?.title ?? r);
  switch (phase.status) {
    case "locked":
      return `Approve ${missing.join(", ")} first.`;
    case "stale":
      return missing.length
        ? `${missing.join(", ")} changed. Approve it again, then regenerate or re-approve this phase.`
        : "An earlier phase changed. Regenerate or approve again.";
    case "ready":
      return "Nothing produced yet. Start below.";
    case "needs_input":
      return "The agent asked questions before it continues.";
    case "draft":
      return "Review the result, edit it or ask for changes, then approve.";
    case "approved":
      return "Approved. Later phases build on this.";
  }
}

// P1 to P3 are the left wing, P4 the body, P5 to P7 the right wing (project requirements, section 2).
export function wingOf(index: number): "left" | "body" | "right" {
  return index < 3 ? "left" : index === 3 ? "body" : "right";
}
