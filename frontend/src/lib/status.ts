import type { PhaseState, PhaseStatus } from "../api/types";

export const STATUS_LABEL: Record<PhaseStatus, string> = {
  locked: "Locked",
  ready: "Ready",
  needs_input: "Needs your answer",
  draft: "Ready for review",
  approved: "Approved",
  stale: "Out of date",
};

/** The status a phase shows: planned wings have no real status yet. */
export type DisplayStatus = PhaseStatus | "planned";

export const displayStatus = (p: Pick<PhaseState, "implemented" | "status">): DisplayStatus =>
  p.implemented ? p.status : "planned";

export const DISPLAY_LABEL: Record<DisplayStatus, string> = { ...STATUS_LABEL, planned: "Planned" };

/** What the developer does at a step, in one word. Shown under each station of the pipeline. */
export const ACTION_LABEL: Record<DisplayStatus, string> = {
  locked: "Locked",
  ready: "Start",
  needs_input: "Answer",
  draft: "Review",
  approved: "Done",
  stale: "Update",
  planned: "Soon",
};

/** What each word means; the legend of the "How it works" panel. */
export const ACTION_MEANING: Record<DisplayStatus, string> = {
  ready: "Your turn: tell the agent what you want.",
  needs_input: "The agent asked questions. Answer them.",
  draft: "A result is ready. Check it, then approve or ask for changes.",
  approved: "Approved. Later steps build on it.",
  stale: "An earlier step changed. Regenerate this one or approve it again.",
  locked: "Approve the step before it first.",
  planned: "Not built yet.",
};

/** Whether the phase waits for the developer (used to draw attention, never as the only cue). */
export const needsDeveloper = (s: DisplayStatus) => s === "needs_input" || s === "draft" || s === "stale";

const titleOf = (id: string, all: PhaseState[]) => all.find((p) => p.id === id)?.title ?? id;

/** One sentence that says what to do next. Derived from the same rules the backend enforces. */
export function statusHint(phase: PhaseState, all: PhaseState[]): string {
  if (!phase.implemented) return "This wing is planned and not built yet.";
  const missing = phase.requires.filter((r) => all.find((p) => p.id === r)?.status !== "approved").map((r) => titleOf(r, all));
  switch (phase.status) {
    case "locked":
      return `Approve ${missing.join(", ")} first.`;
    case "stale": {
      const cause = phase.stale_cause ? titleOf(phase.stale_cause, all) : "An earlier phase";
      return missing.length
        ? `${cause} changed. Approve ${missing.join(", ")} again, then regenerate or re-approve this phase.`
        : `${cause} changed since this was made. Regenerate it, or approve it again if it still fits.`;
    }
    case "ready":
      return "Nothing produced yet. Start below.";
    case "needs_input":
      return "The agent asked questions before it continues. Answer them below.";
    case "draft":
      return "Review the result. Edit it or ask for changes, then approve.";
    case "approved":
      return "Approved. Later phases build on this.";
  }
}

// P1 to P3 are the left wing, P4 the body, P5 to P7 the right wing (project requirements, section 2).
export function wingOf(index: number): "left" | "body" | "right" {
  return index < 3 ? "left" : index === 3 ? "body" : "right";
}

const EVENT_LABEL: Record<string, string> = {
  "project.created": "Project created",
  "action.started": "Started",
  "action.finished": "Finished",
  "agent.llm_call": "Agent replied",
  "artifact.saved": "Saved",
  "phase.stale": "Out of date",
  "phase.approved": "Approved",
  "phase.reopened": "Reopened",
  "phase.error": "Error",
};

export const eventLabel = (kind: string) => EVENT_LABEL[kind] ?? kind;
