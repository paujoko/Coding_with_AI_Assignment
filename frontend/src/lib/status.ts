import type { PhaseState, PhaseStatus } from "../api/types";

// The backend's phase statuses never reach the screen as words: the step list and the step screens speak in marks
// and sentences from lib/flow.ts. What is left here: the status a phase shows in the logo mark, and event names.

/** The status a phase shows: planned wings have no real status yet. */
export type DisplayStatus = PhaseStatus | "planned";

export const displayStatus = (p: Pick<PhaseState, "implemented" | "status">): DisplayStatus =>
  p.implemented ? p.status : "planned";

const EVENT_LABEL: Record<string, string> = {
  "project.created": "Project created",
  "action.started": "Started",
  "action.finished": "Finished",
  "agent.llm_call": "Agent replied",
  "agent.tool_call": "Tool used",
  "attachment.added": "Document added",
  "artifact.saved": "Saved",
  "phase.stale": "Needs a redo",
  "phase.approved": "Accepted",
  "phase.reopened": "Reopened",
  "phase.error": "Error",
  "change.advance": "Change carried on",
  "change.stopped": "Change waits",
};

export const eventLabel = (kind: string) => EVENT_LABEL[kind] ?? kind;
