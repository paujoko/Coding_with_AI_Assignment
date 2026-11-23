import type { CatchUpResult, Project } from "../api/types";
import { runUpdate, type UpdateRun } from "./catchup";

const project: Project = { id: "p", name: "p", created_at: "", phases: [] };
const titles: Record<string, string> = { design: "Design", refinement: "Design refinement", codegen: "Code generation", testing: "Testing" };
const titleOf = (id: string) => titles[id] ?? id;

const result = (phase: string, remaining: string[], over: Partial<CatchUpResult> = {}): CatchUpResult => ({
  project,
  ran: [{ phase, action: "revise", label: "Revise", status: "approved", reply: "ok" }],
  approved: phase,
  stopped_reason: null,
  remaining,
  done: remaining.length === 0,
  ...over,
});

function go(results: (CatchUpResult | Error)[], over: Partial<Parameters<typeof runUpdate>[0]> = {}) {
  const seen: UpdateRun[] = [];
  const calls: boolean[] = [];
  const queue = [...results];
  const promise = runUpdate({
    stale: ["design", "refinement", "codegen", "testing"],
    titleOf,
    call: async (approve) => {
      calls.push(approve);
      const next = queue.shift();
      if (!next) throw new Error("no more answers");
      if (next instanceof Error) throw next;
      return next;
    },
    onUpdate: (r) => seen.push(r),
    ...over,
  });
  return { promise, seen, calls };
}

test("loops one phase per call until nothing is out of date, with live progress 'n of N'", async () => {
  const refreshed: string[][] = [];
  const { promise, seen, calls } = go([result("design", ["refinement", "codegen", "testing"]), result("refinement", ["codegen", "testing"]), result("codegen", ["testing"]), result("testing", [])], {
    onResult: (r) => void refreshed.push(r.remaining),
  });
  const run = await promise;
  expect(calls).toEqual([true, true, true, true]);
  expect(refreshed).toHaveLength(4); // project, phase data and trace are loaded again after every call
  expect(run).toMatchObject({ active: false, complete: true, stopped: null, total: 4 });
  expect(run.steps.map((s) => [s.title, s.approved])).toEqual([
    ["Design", true],
    ["Design refinement", true],
    ["Code generation", true],
    ["Testing", true],
  ]);
  const running = seen.filter((r) => r.current).map((r) => `${r.current!.title} ${r.current!.index}`);
  expect(running).toEqual(["Design 1", "Design refinement 2", "Code generation 3", "Testing 4"]);
});

test("a stop reason from the backend ends the loop and names the phase to look at", async () => {
  const { promise, calls } = go([result("design", ["refinement", "codegen", "testing"]), result("refinement", ["codegen", "testing"], { approved: null, stopped_reason: "Design refinement has open findings. Look at them." })]);
  const run = await promise;
  expect(calls).toHaveLength(2);
  expect(run).toMatchObject({ complete: false, stopped: "Design refinement has open findings. Look at them.", stoppedPhase: "codegen" });
  expect(run.steps[1].approved).toBe(false);
});

test("Stop ends it after the running step, in the developer's words", async () => {
  let stop = false;
  const { promise, calls } = go([result("design", ["refinement", "codegen", "testing"]), result("refinement", ["codegen", "testing"])], {
    stopRequested: () => stop,
    onResult: () => {
      stop = true;
    },
  });
  const run = await promise;
  expect(calls).toHaveLength(1);
  expect(run.stopped).toBe("You stopped the update after Design.");
  expect(run.stoppedPhase).toBeNull();
});

test("Update this step only makes one call and does not count the rest as a stop", async () => {
  const { promise, calls } = go([result("design", ["refinement", "codegen", "testing"])], { only: true });
  const run = await promise;
  expect(calls).toHaveLength(1);
  expect(run).toMatchObject({ only: true, total: 1, stopped: null, complete: false });
});

test("a refused request (409) ends the run and is kept for the card", async () => {
  const { promise } = go([new Error("An agent is already working on this project.")]);
  const run = await promise;
  expect(run).toMatchObject({ failed: "An agent is already working on this project.", active: false, stoppedPhase: "design" });
});

test("a backend that does not move on is stopped instead of looping", async () => {
  const same = ["design", "refinement", "codegen", "testing"];
  const { promise, calls } = go([result("design", same), result("design", same)]);
  const run = await promise;
  expect(calls.length).toBe(1);
  expect(run.stopped).toBe("Design did not change. Open it and update it there.");
});

test("a failed reload does not hide that the step went through", async () => {
  const { promise } = go([result("design", [])], {
    onResult: () => {
      throw new Error("reload failed");
    },
  });
  expect((await promise).complete).toBe(true);
});
