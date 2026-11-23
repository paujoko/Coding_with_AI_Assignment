import type { Change, ChangeAdvance, ChangeNext, OpenChange, ReceiptEntry, ReceiptPhase } from "../api/types";

// A change carried through the phases (API 9): the words the tracker uses, and the loop behind "Carry it through".
// Progress, next step and receipt are computed by the backend; nothing here guesses a state.

export const CHANGE_KIND_LABEL: Record<string, string> = { bug: "Bug", change: "Change", new_requirement: "New requirement" };

// What a phase makes, as the object of a sentence: "Update the design", "Approve the tests".
const PHASE_OBJECT: Record<string, string> = {
  requirements: "the requirements",
  design: "the design",
  refinement: "the refined design",
  codegen: "the code",
  testing: "the tests",
  deployment: "the deployment files",
};

export const phaseObject = (phase: string, title: string) => PHASE_OBJECT[phase] ?? title.toLowerCase();

/** The step of the change the developer is at, counted from 1 ("step 2 of 6"). */
export const changeStepNumber = (c: Pick<OpenChange, "done" | "total">) => Math.max(1, Math.min(c.done + 1, c.total));

/** "2 of 6": where an open change stands. */
export const changeStepOf = (c: Pick<OpenChange, "done" | "total">) => `${changeStepNumber(c)} of ${Math.max(c.total, 1)}`;

/** The button for the next step, named for what it does. */
export function nextLabel(next: ChangeNext): string {
  const what = phaseObject(next.phase, next.title);
  if (next.kind === "approve") return `Approve ${what}`;
  if (next.kind === "input") return `Answer in ${next.title}`;
  if (next.kind === "blocked") return `Open ${next.title}`;
  return next.steps.length > 1 && next.phase === "testing" ? `Update and run ${what}` : `Update ${what}`;
}

/** While it runs: "Updating the design". */
export function runningLabel(next: ChangeNext): string {
  const what = phaseObject(next.phase, next.title);
  return next.kind === "approve" ? `Approving ${what}` : `Updating ${what}`;
}

const KIND_OF_ARTIFACT: Record<string, string> = {
  requirements: "Requirements",
  diagram: "Diagram",
  review: "Review",
  source_file: "Code",
  test_file: "Test",
  test_report: "Test report",
  deployment_file: "Deployment file",
  deployment_check: "Deployment check",
  known_gaps: "Known gaps",
};

export const artifactKindLabel = (kind: string) => KIND_OF_ARTIFACT[kind] ?? kind.replace(/_/g, " ");

export interface ReceiptTotals {
  updated: number; // revisions that really differ
  identical: number; // written again without a difference
  added: number;
  removed: number;
  phases: number; // phases with at least one entry
}

export function receiptTotals(receipt: ReceiptPhase[]): ReceiptTotals {
  const t: ReceiptTotals = { updated: 0, identical: 0, added: 0, removed: 0, phases: 0 };
  for (const r of receipt) {
    const real = r.updated.filter((e) => e.changed !== false).length;
    t.updated += real;
    t.identical += r.updated.length - real;
    t.added += r.added.length;
    t.removed += r.removed.length;
    if (r.updated.length + r.added.length + r.removed.length > 0) t.phases += 1;
  }
  return t;
}

const count = (n: number, word: string) => `${n} ${word}`;

/** "5 updated, 2 added, 1 removed": only what there is. Empty when nothing was touched. */
export function totalsText(t: Pick<ReceiptTotals, "updated" | "added" | "removed">): string {
  return [t.updated ? count(t.updated, "updated") : "", t.added ? count(t.added, "added") : "", t.removed ? count(t.removed, "removed") : ""]
    .filter(Boolean)
    .join(", ");
}

export type ReceiptRow = ReceiptEntry & { what: "updated" | "identical" | "added" | "removed" };

/** The entries of one phase in reading order: real updates, new ones, removed ones, identical rewrites last. */
export function receiptRows(r: ReceiptPhase): ReceiptRow[] {
  return [
    ...r.updated.filter((e) => e.changed !== false).map((e) => ({ ...e, what: "updated" as const })),
    ...r.added.map((e) => ({ ...e, what: "added" as const })),
    ...r.removed.map((e) => ({ ...e, what: "removed" as const })),
    ...r.updated.filter((e) => e.changed === false).map((e) => ({ ...e, what: "identical" as const })),
  ];
}

/** The maintenance answer that created a tracked change repeats what the tracker shows. Keep what it says about the change. */
export function changeReplyText(text: string): string {
  const kept = text
    .split("\n")
    .filter((line) => !/^\s*Phases that move:/i.test(line) && !/with the button below/i.test(line));
  return kept.join("\n").trim() || text;
}

// ---------- Carrying a change through ----------

export interface CarryStep {
  phase: string;
  title: string;
  ran: string[]; // labels of the actions that ran in this call
  approved: boolean; // Wings approved the phase in this call
  seconds: number;
}

/** One press of a tracker button: a single step, or the loop until something stops it. */
export interface CarryRun {
  change: number;
  through: boolean; // "Carry it through": Wings approves each step whose checks pass
  active: boolean;
  current: { phase: string; title: string; doing: string; since: string } | null;
  steps: CarryStep[];
  stopping: boolean; // the developer asked to stop after the running step
  stopped: string | null; // why it stopped, in the backend's or the developer's words
  stoppedPhase: string | null; // the phase to look at
  failed: string | null; // the request itself failed (409, backend unreachable)
  complete: boolean; // the change is closed
}

export interface CarryOptions {
  change: Change;
  through: boolean;
  advance: (number: number, approve: boolean) => Promise<ChangeAdvance>;
  onUpdate: (run: CarryRun) => void;
  onAdvanced?: (result: ChangeAdvance) => Promise<void> | void; // refresh project, phase data and trace
  stopRequested?: () => boolean;
  now?: () => number;
}

const MAX_CALLS = 12; // six phases; a backend that never stops must not keep the page busy forever

/** Runs `advance` once (one step) or until it stops (through). One phase per call; never throws. */
export async function carryChange(o: CarryOptions): Promise<CarryRun> {
  const now = o.now ?? Date.now;
  const asked = () => o.stopRequested?.() ?? false;
  let change = o.change;
  let run: CarryRun = {
    change: change.number,
    through: o.through,
    active: true,
    current: null,
    steps: [],
    stopping: false,
    stopped: null,
    stoppedPhase: null,
    failed: null,
    complete: false,
  };
  const update = (patch: Partial<CarryRun>) => {
    run = { ...run, ...patch, stopping: patch.active === false ? false : asked() };
    o.onUpdate(run);
  };

  for (let calls = 0; calls < MAX_CALLS; calls += 1) {
    const next = change.next;
    if (change.state !== "open" || !next) break;
    if (next.kind === "input" || next.kind === "blocked") {
      update({ stopped: next.reason ?? `${next.title} needs you.`, stoppedPhase: next.phase });
      break;
    }
    const started = now();
    update({ current: { phase: next.phase, title: next.title, doing: runningLabel(next), since: new Date(started).toISOString() } });
    let result: ChangeAdvance;
    try {
      // One step at a time leaves the approval to the developer; approving is its own step.
      result = await o.advance(change.number, o.through || next.kind === "approve");
    } catch (e) {
      update({ current: null, failed: e instanceof Error ? e.message : String(e), stoppedPhase: next.phase });
      break;
    }
    change = result.change;
    const step: CarryStep = {
      phase: next.phase,
      title: next.title,
      ran: result.ran.map((r) => r.label || r.action),
      approved: result.approved === next.phase,
      seconds: Math.max(0, Math.round((now() - started) / 1000)),
    };
    update({ current: null, steps: [...run.steps, step] });
    try {
      await o.onAdvanced?.(result);
    } catch {
      /* the step itself went through; a failed reload must not hide that */
    }
    if (result.stopped_reason !== null || change.state !== "open") {
      // "Ready for review" after a single step is what the developer asked for, not a stop.
      // A closed gate or open questions are said by the change's own next step (`next.reason`).
      const expected = !o.through && result.ran.length > 0 && result.ran.every((r) => r.status === "draft");
      if (result.stopped_reason !== null && !expected && change.state === "open")
        update({ stopped: result.stopped_reason, stoppedPhase: change.next?.phase ?? next.phase });
      break;
    }
    if (!o.through) break;
    if (asked()) {
      update({ stopped: `You stopped it after ${next.title}.`, stoppedPhase: null });
      break;
    }
  }
  update({ active: false, current: null, complete: change.state === "complete" });
  return run;
}

/** "0:42" for a finished step. */
export const duration = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

// ---------- Maintenance in the sidebar, the badge and the project switcher ----------

/** The word at the Maintenance step. While a change is carried through it says where the change stands.
 * Otherwise Maintenance is simply there to be used: `null` means no word (it reads as ready), never "Start" or "Review" forever. */
export function maintenanceWord(status: string, open: OpenChange | null | undefined): string | null {
  if (status === "planned" || status === "locked") return status === "planned" ? "Soon" : "Locked";
  if (open) return `Step ${changeStepOf(open)}`;
  if (status === "needs_input") return "Answer";
  return status === "stale" ? "Check" : null; // out of date: run the consistency check again
}

/** One sentence for tooltips and the strip above other phases: "Change #1: step 3 of 6, next: Code generation". */
export function changeLine(open: OpenChange, phases: { id: string; title: string }[]): string {
  const next = open.next_phase ? (phases.find((p) => p.id === open.next_phase)?.title ?? open.next_phase) : null;
  return `Change #${open.number}: step ${changeStepOf(open)}${next ? `, next: ${next}` : ""}`;
}
