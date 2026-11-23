import { useEffect, useRef, useState } from "react";
import type { Change, ChangeAdvance } from "../api/types";
import { carryChange, type CarryRun } from "./changes";

interface Options {
  projectId: string | null;
  /** App's busy handling: navigation is disabled and nothing else can be sent while the work runs. */
  guarded: (work: () => Promise<void>) => Promise<boolean>;
  advance: (projectId: string, number: number, approve: boolean) => Promise<ChangeAdvance>;
  onAdvanced: (result: ChangeAdvance) => Promise<void>; // after every step: project, phase data, trace
  onFailed: (projectId: string) => Promise<void>; // the request failed: look at the project again
}

// State behind the change tracker's buttons: the run in progress (or the last one), and "Stop after this step".
export function useCarry(o: Options) {
  const [run, setRun] = useState<CarryRun | null>(null);
  const stop = useRef(false);
  const latest = useRef(o);
  latest.current = o;

  useEffect(() => {
    setRun(null);
  }, [o.projectId]);

  const start = (change: Change, through: boolean) => {
    const pid = o.projectId;
    if (!pid) return Promise.resolve(false);
    stop.current = false;
    return o.guarded(async () => {
      const done = await carryChange({
        change,
        through,
        advance: (number, approve) => latest.current.advance(pid, number, approve),
        onUpdate: (r) => {
          if (latest.current.projectId === pid) setRun(r);
        },
        onAdvanced: (result) => latest.current.onAdvanced(result),
        stopRequested: () => stop.current,
      });
      if (done.failed) await latest.current.onFailed(pid).catch(() => undefined);
    });
  };

  const requestStop = () => {
    stop.current = true;
    setRun((r) => (r && r.active ? { ...r, stopping: true } : r));
  };

  return { run, start, requestStop };
}
