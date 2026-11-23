import type { Change, ChangeAdvance, ChangeNext, ChangePhase, Project } from "../api/types";

// Test data in the shape of GET /projects/{id}/changes (docs/code/api.md, "Changes carried through the phases").

const PHASES: [string, string][] = [
  ["requirements", "Requirements"],
  ["design", "Design"],
  ["refinement", "Design refinement"],
  ["codegen", "Code generation"],
  ["testing", "Testing"],
  ["deployment", "Deployment"],
];

/** A change with `done` phases finished; the next one is current, the rest wait. Six done: complete. */
export function makeChange(done: number, over: Partial<Change> = {}): Change {
  const phases: ChangePhase[] = PHASES.map(([phase, title], i) => ({
    phase,
    title,
    state: i < done ? "done" : i === done ? "current" : "waiting",
    status: i < done ? "approved" : "stale",
    updated: i < done,
  }));
  const current = PHASES[done];
  const next: ChangeNext | null = current
    ? { phase: current[0], title: current[1], kind: "run", action: "revise", label: "Revise", input: {}, steps: [{ phase: current[0], action: "revise", label: "Revise", input: {} }], reason: null }
    : null;
  return {
    number: 1,
    artifact_id: "change-1",
    kind: "change",
    request: "Tasks need a priority",
    summary: "Tasks get a priority.",
    affected: ["REQ-001", "REQ-002"],
    state: current ? "open" : "complete",
    started_at: "2026-11-23T10:26:30Z",
    completed_at: current ? null : "2026-11-23T10:40:00Z",
    progress: { phases, current: current?.[0] ?? null, started: done > 0, complete: !current, done, total: 6 },
    next,
    receipt: PHASES.map(([phase, title], i) => ({
      phase,
      title,
      updated: i < done ? [{ id: `${phase}-a`, title: `${title} artifact`, kind: "diagram", path: `${phase}/a.puml`, before: 1, after: 2, changed: true }] : [],
      added: [],
      removed: [],
    })),
    ...over,
  };
}

export const projectWith = (open: Change | null): Project => ({
  id: "todo",
  name: "Todo",
  created_at: "",
  phases: [],
  open_change: open && open.state === "open" ? { number: open.number, done: open.progress.done, total: open.progress.total, next_phase: open.progress.current } : null,
});

/** The answer to one advance call. */
export function advanced(change: Change, over: Partial<ChangeAdvance> = {}): ChangeAdvance {
  return { project: projectWith(change), change, ran: [{ phase: "x", action: "revise", label: "Revise", status: "draft", reply: "ok" }], approved: null, stopped_reason: null, ...over };
}
