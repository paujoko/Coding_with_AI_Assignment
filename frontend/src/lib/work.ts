/**
 * The step an agent works on, while the developer may look at other steps (read-only) meanwhile.
 * `App.tsx` keeps one `Work`; these pure functions decide where the screen goes and what the notice says.
 */
export interface Work {
  project: string;
  phase: string; // the step the agent works on; Accept and "Redo all" move it on
  state: "running" | "ready" | "failed"; // ready and failed: it ended while the developer looked elsewhere
}

export interface Shown {
  view: string; // "phase", "trace", "folder", "activity"
  phase: string | null;
}

const onStep = (work: Work, shown: Shown) => shown.view === "phase" && shown.phase === work.phase;

/** Does a step change made by the work move the screen? Only when the developer watches the working step. */
export function follows(work: Work | null, shown: Shown): boolean {
  return !work || onStep(work, shown);
}

/** The work goes on in another step (Accept starts the next one, Redo all takes the next stale step). */
export function moveWork(work: Work | null, phase: string): Work | null {
  return work ? { ...work, phase } : null;
}

/** The slim notice above every other screen: which step, and whether it still runs. Null on the step itself. */
export function noticeFor(work: Work | null, shown: Shown): { phase: string; state: Work["state"] } | null {
  if (!work || onStep(work, shown)) return null;
  return { phase: work.phase, state: work.state };
}

/** When the work ends: nothing to say if the developer watched it, else the notice says it is ready (or failed). */
export function afterWork(work: Work | null, ok: boolean, shown: Shown): Work | null {
  if (!work || onStep(work, shown)) return null;
  return { ...work, state: ok ? "ready" : "failed" };
}
