import { useEffect, useRef, useState } from "react";
import type { CatchUpResult } from "../api/types";
import { runUpdate, type UpdateRun } from "./catchup";

interface Options {
  projectId: string | null;
  /** App's busy handling: navigation is disabled and nothing else can be sent while the work runs. */
  guarded: (work: () => Promise<void>) => Promise<boolean>;
  catchUp: (projectId: string, approve: boolean) => Promise<CatchUpResult>;
  titleOf: (phase: string) => string;
  onResult: (result: CatchUpResult) => Promise<void>; // after every step: project, phase data, trace
  onFailed: (projectId: string) => Promise<void>; // the request failed: look at the project again
}

// State behind "Update all N steps": the run in progress (or the last one), and Stop.
export function useUpdate(o: Options) {
  const [run, setRun] = useState<UpdateRun | null>(null);
  const stop = useRef(false);
  const latest = useRef(o);
  latest.current = o;

  useEffect(() => {
    setRun(null);
  }, [o.projectId]);

  const start = (stale: string[], only = false) => {
    const pid = o.projectId;
    if (!pid || stale.length === 0) return Promise.resolve(false);
    stop.current = false;
    return o.guarded(async () => {
      const done = await runUpdate({
        stale,
        only,
        titleOf: (p) => latest.current.titleOf(p),
        call: (approve) => latest.current.catchUp(pid, approve),
        onUpdate: (r) => {
          if (latest.current.projectId === pid) setRun(r);
        },
        onResult: (result) => latest.current.onResult(result),
        stopRequested: () => stop.current,
      });
      if (done.failed) await latest.current.onFailed(pid).catch(() => undefined);
    });
  };

  const requestStop = () => {
    stop.current = true;
    setRun((r) => (r && r.active ? { ...r, stopping: true } : r));
  };

  const clear = () => setRun(null);

  return { run, start, requestStop, clear };
}
