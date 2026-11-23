import type { CatchUpResult } from "../api/types";

// "Update all N steps": the loop over POST /catch-up. One phase per call (the backend updates the first out-of-date
// phase, runs its own refresh and approves it when its code checks pass). Never throws: a stop is part of the run.

export interface UpdateStep {
  phase: string;
  title: string;
  ran: string[]; // labels of the actions that ran in this call
  approved: boolean;
  seconds: number;
}

export interface UpdateRun {
  active: boolean;
  only: boolean; // "Update this step only": one call
  total: number; // how many steps were out of date when it started
  current: { phase: string; title: string; index: number; since: string } | null; // index counts from 1
  steps: UpdateStep[];
  stopping: boolean; // the developer pressed Stop; it ends when the running step has answered
  stopped: string | null; // why it stopped, in plain words
  stoppedPhase: string | null; // the phase to look at
  failed: string | null; // the request itself failed (409, backend unreachable)
  complete: boolean; // nothing is out of date any more
}

export interface UpdateOptions {
  stale: string[]; // phase ids that are out of date now, in pipeline order
  only?: boolean;
  titleOf: (phase: string) => string;
  call: (approve: boolean) => Promise<CatchUpResult>;
  onUpdate: (run: UpdateRun) => void;
  onResult?: (result: CatchUpResult) => Promise<void> | void; // refresh project, phase data and trace
  stopRequested?: () => boolean;
  now?: () => number;
}

const MAX_CALLS = 12; // six phases; a backend that never finishes must not keep the page busy forever

export async function runUpdate(o: UpdateOptions): Promise<UpdateRun> {
  const now = o.now ?? Date.now;
  const asked = () => o.stopRequested?.() ?? false;
  const only = o.only ?? false;
  let remaining = [...o.stale];
  let run: UpdateRun = {
    active: true,
    only,
    total: only ? Math.min(1, remaining.length) : remaining.length,
    current: null,
    steps: [],
    stopping: false,
    stopped: null,
    stoppedPhase: null,
    failed: null,
    complete: false,
  };
  const update = (patch: Partial<UpdateRun>) => {
    run = { ...run, ...patch, stopping: patch.active === false ? false : asked() };
    o.onUpdate(run);
  };

  for (let calls = 0; calls < MAX_CALLS; calls += 1) {
    const phase = remaining[0];
    if (!phase) break;
    const started = now();
    update({ current: { phase, title: o.titleOf(phase), index: run.steps.length + 1, since: new Date(started).toISOString() } });
    let result: CatchUpResult;
    try {
      result = await o.call(true);
    } catch (e) {
      update({ current: null, failed: e instanceof Error ? e.message : String(e), stoppedPhase: phase });
      break;
    }
    const ranPhase = result.ran[0]?.phase ?? phase;
    run = {
      ...run,
      steps: [
        ...run.steps,
        { phase: ranPhase, title: o.titleOf(ranPhase), ran: result.ran.map((r) => r.label || r.action), approved: result.approved === ranPhase, seconds: Math.max(0, Math.round((now() - started) / 1000)) },
      ],
    };
    update({ current: null });
    try {
      await o.onResult?.(result);
    } catch {
      /* the step itself went through; a failed reload must not hide that */
    }
    if (result.stopped_reason !== null) {
      update({ stopped: result.stopped_reason, stoppedPhase: result.remaining[0] ?? ranPhase });
      break;
    }
    if (result.done || result.remaining.length === 0) {
      update({ complete: true });
      break;
    }
    const before = remaining;
    remaining = result.remaining;
    if (!only) update({ total: Math.max(run.total, run.steps.length + remaining.length) });
    if (only) break;
    if (remaining.length === before.length && remaining[0] === before[0]) {
      update({ stopped: `${o.titleOf(remaining[0])} did not change. Open it and update it there.`, stoppedPhase: remaining[0] });
      break;
    }
    if (asked()) {
      update({ stopped: `You stopped the update after ${o.titleOf(ranPhase)}.`, stoppedPhase: null });
      break;
    }
  }
  update({ active: false, current: null });
  return run;
}
