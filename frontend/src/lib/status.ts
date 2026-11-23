import type { PhaseState, PhaseStatus } from "../api/types";

export const STATUS_LABEL: Record<PhaseStatus, string> = {
  locked: "Locked",
  ready: "To do",
  needs_input: "Your answer needed",
  draft: "Ready for review",
  approved: "Done",
  stale: "Out of date",
};

/** The status a phase shows: planned wings have no real status yet. */
export type DisplayStatus = PhaseStatus | "planned";

export const displayStatus = (p: Pick<PhaseState, "implemented" | "status">): DisplayStatus =>
  p.implemented ? p.status : "planned";

export const DISPLAY_LABEL: Record<DisplayStatus, string> = { ...STATUS_LABEL, planned: "Planned" };

/** The word next to a step in the sidebar: one word, shown only where the developer has to act. */
export const ACTION_LABEL: Record<DisplayStatus, string> = {
  locked: "Locked",
  ready: "Start",
  needs_input: "Answer",
  draft: "Review",
  approved: "Done",
  stale: "Update",
  planned: "Soon",
};

/** The status word in the badge next to a step's title: the same words the next-step card uses. */
export const BADGE_LABEL: Record<DisplayStatus, string> = { ...DISPLAY_LABEL };

/** What each sidebar word means; the legend of the "How it works" dialog. One short line each. */
export const ACTION_MEANING: Record<DisplayStatus, string> = {
  ready: "Your turn. Tell the agent what you want.",
  needs_input: "The agent asked questions. Answer them.",
  draft: "A result is ready. Check it, then approve it.",
  approved: "Approved. Later steps build on it.",
  stale: "An earlier step changed. Update it.",
  locked: "Approve the step before it first.",
  planned: "Not built yet.",
};

/** The phase a project waits on: the first implemented one that is not approved yet. */
export function focusPhase(phases: PhaseState[]): PhaseState {
  return phases.find((p) => p.implemented && p.can_run && p.status !== "approved") ?? phases[0];
}

/** The program can be started: everything up to and including Deployment is approved (Maintenance comes after). */
export function readyToRun(phases: PhaseState[]): boolean {
  const built = phases.filter((p) => p.implemented && p.id !== "maintenance");
  return built.some((p) => p.id === "deployment") && built.every((p) => p.status === "approved");
}

/** Whether the phase waits for the developer (used to draw attention, never as the only cue). */
export const needsDeveloper = (s: DisplayStatus) => s === "needs_input" || s === "draft" || s === "stale";

const titleOf = (id: string, all: PhaseState[]) => all.find((p) => p.id === id)?.title ?? id;

/** One short sentence for what holds a step back (locked, or out of date behind an unfinished step). */
export function statusHint(phase: PhaseState, all: PhaseState[]): string {
  if (!phase.implemented) return "Not built yet.";
  const missing = phase.requires.filter((r) => all.find((p) => p.id === r)?.status !== "approved").map((r) => titleOf(r, all));
  switch (phase.status) {
    case "locked":
      return `Approve ${missing.join(", ")} first.`;
    case "stale": {
      const cause = phase.stale_cause ? titleOf(phase.stale_cause, all) : "An earlier step";
      return missing.length ? `${cause} changed. Finish ${missing.join(", ")} first.` : `${cause} changed after this was made.`;
    }
    case "ready":
      return "Nothing made yet.";
    case "needs_input":
      return "Answer the agent's questions below.";
    case "draft":
      return "Check the result, then approve.";
    case "approved":
      return "Approved.";
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
  "agent.tool_call": "Tool used",
  "attachment.added": "Document added",
  "artifact.saved": "Saved",
  "phase.stale": "Out of date",
  "phase.approved": "Approved",
  "phase.reopened": "Reopened",
  "phase.error": "Error",
  "change.advance": "Change carried on",
  "change.stopped": "Change waits",
};

export const eventLabel = (kind: string) => EVENT_LABEL[kind] ?? kind;
