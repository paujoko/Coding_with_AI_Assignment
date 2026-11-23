import type { ChangeAdvance } from "../api/types";
import { advanced, makeChange } from "./changes.fixture";
import { carryChange, type CarryRun, changeLine, changeReplyText, changeStepOf, maintenanceWord, nextLabel, receiptRows, receiptTotals, totalsText } from "./changes";

// A backend that finishes one phase per call, as POST /changes/{n}/advance does.
function backend(from: number, stopAt?: { done: number; reason: string }) {
  let done = from;
  const calls: { number: number; approve: boolean }[] = [];
  const advance = async (number: number, approve: boolean): Promise<ChangeAdvance> => {
    calls.push({ number, approve });
    const phase = makeChange(done).next!.phase;
    if (stopAt && done === stopAt.done) return advanced(makeChange(done), { stopped_reason: stopAt.reason });
    if (!approve) {
      const waiting = makeChange(done);
      return advanced({ ...waiting, next: { ...waiting.next!, kind: "approve", steps: [] } }, { stopped_reason: `${phase} is ready for review. Approve it to continue.` });
    }
    done += 1;
    return advanced(makeChange(done), { approved: phase });
  };
  return { advance, calls };
}

test("carry it through calls advance once per phase until the change is complete", async () => {
  const { advance, calls } = backend(1);
  const seen: CarryRun[] = [];
  const refreshed: number[] = [];
  const run = await carryChange({
    change: makeChange(1),
    through: true,
    advance,
    onUpdate: (r) => seen.push(r),
    onAdvanced: (r) => {
      refreshed.push(r.change.progress.done);
    },
  });
  expect(calls).toHaveLength(5); // design to deployment, one phase per call
  expect(calls.every((c) => c.approve)).toBe(true);
  expect(refreshed).toEqual([2, 3, 4, 5, 6]); // project, phase data and trace are loaded again after every step
  expect(run).toMatchObject({ active: false, complete: true, stopped: null, failed: null });
  expect(run.steps.map((s) => s.phase)).toEqual(["design", "refinement", "codegen", "testing", "deployment"]);
  expect(run.steps.every((s) => s.approved)).toBe(true);
  // While a phase runs, the run says which one and since when.
  expect(seen.find((r) => r.current)?.current).toMatchObject({ phase: "design", doing: "Updating the design" });
  expect(seen.at(-1)).toBe(run);
});

test("the loop stops with the reason the backend gives and names the phase to look at", async () => {
  const { advance, calls } = backend(3, { done: 4, reason: "Some tests do not pass. Fix the code or the tests." });
  const run = await carryChange({ change: makeChange(3), through: true, advance, onUpdate: () => {} });
  expect(calls).toHaveLength(2); // code generation went through, testing stopped
  expect(run).toMatchObject({ active: false, complete: false, stopped: "Some tests do not pass. Fix the code or the tests.", stoppedPhase: "testing" });
});

test("stop after this step ends the loop once the running phase has finished", async () => {
  const { advance, calls } = backend(1);
  let stop = false;
  const run = await carryChange({
    change: makeChange(1),
    through: true,
    advance: async (n, a) => {
      stop = true; // pressed while the first phase runs
      return advance(n, a);
    },
    onUpdate: () => {},
    stopRequested: () => stop,
  });
  expect(calls).toHaveLength(1);
  expect(run.stopped).toBe("You stopped it after Design.");
  expect(run.stoppedPhase).toBeNull(); // nothing to look at: the next step is simply the next button
  expect(run.stopping).toBe(false);
});

test("a refused or failed request ends the run with the error, without throwing", async () => {
  const run = await carryChange({
    change: makeChange(2),
    through: true,
    advance: async () => {
      throw new Error("Another action is still running on this project.");
    },
    onUpdate: () => {},
  });
  expect(run).toMatchObject({ active: false, failed: "Another action is still running on this project.", stoppedPhase: "refinement", steps: [] });
});

test("a backend that never stops cannot keep the page busy forever", async () => {
  let calls = 0;
  const run = await carryChange({
    change: makeChange(1),
    through: true,
    advance: async () => {
      calls += 1;
      return advanced(makeChange(1));
    },
    onUpdate: () => {},
  });
  expect(calls).toBe(12);
  expect(run.active).toBe(false);
});

test("one step runs the phase without approving; being ready for review is not a stop", async () => {
  const { advance, calls } = backend(1);
  const run = await carryChange({ change: makeChange(1), through: false, advance, onUpdate: () => {} });
  expect(calls).toEqual([{ number: 1, approve: false }]);
  expect(run).toMatchObject({ active: false, stopped: null, complete: false });
  expect(run.steps).toMatchObject([{ phase: "design", approved: false, ran: ["Revise"] }]);
});

test("one step on a phase that waits for approval approves it", async () => {
  const { advance, calls } = backend(1);
  const waiting = makeChange(1);
  await carryChange({ change: { ...waiting, next: { ...waiting.next!, kind: "approve", steps: [] } }, through: false, advance, onUpdate: () => {} });
  expect(calls).toEqual([{ number: 1, approve: true }]);
});

test("one step whose action fails says why", async () => {
  const reason = "Design: 'Revise' did not finish. The model did not answer.";
  const run = await carryChange({
    change: makeChange(1),
    through: false,
    advance: async () => advanced(makeChange(1), { ran: [], stopped_reason: reason }),
    onUpdate: () => {},
  });
  expect(run).toMatchObject({ stopped: reason, stoppedPhase: "design", failed: null });
});

test("open questions stop the loop before anything is sent", async () => {
  const { advance, calls } = backend(0);
  const asked = makeChange(0);
  const change = { ...asked, next: { ...asked.next!, kind: "input" as const, reason: "Requirements has open questions. Answer them in the phase, then continue." } };
  const run = await carryChange({ change, through: true, advance, onUpdate: () => {} });
  expect(calls).toHaveLength(0);
  expect(run.stopped).toMatch(/open questions/);
  expect(run.stoppedPhase).toBe("requirements");
});

test("buttons are named for what the step does", () => {
  const at = (done: number) => makeChange(done).next!;
  expect(nextLabel(at(1))).toBe("Update the design");
  expect(nextLabel({ ...at(4), kind: "approve" })).toBe("Approve the tests");
  expect(nextLabel({ ...at(4), steps: [...at(4).steps, ...at(4).steps] })).toBe("Update and run the tests");
  expect(nextLabel({ ...at(0), kind: "input" })).toBe("Answer in Requirements");
  expect(nextLabel({ ...at(4), kind: "blocked" })).toBe("Open Testing");
});

test("the receipt counts real updates and keeps identical rewrites apart", () => {
  const change = makeChange(2);
  change.receipt[1].updated.push({ id: "same", title: "Same", kind: "diagram", path: null, before: 1, after: 2, changed: false });
  change.receipt[1].added.push({ id: "new", title: "New", kind: "diagram", path: null, before: null, after: 1, changed: true });
  const totals = receiptTotals(change.receipt);
  expect(totals).toEqual({ updated: 2, identical: 1, added: 1, removed: 0, phases: 2 });
  expect(totalsText(totals)).toBe("2 updated, 1 added");
  expect(receiptRows(change.receipt[1]).map((r) => r.what)).toEqual(["updated", "added", "identical"]);
});

test("where a change stands, in words", () => {
  expect(changeStepOf({ done: 1, total: 6 })).toBe("2 of 6");
  expect(changeStepOf({ done: 6, total: 6 })).toBe("6 of 6"); // the moment before it is closed
  const phases = [{ id: "codegen", title: "Code generation" }];
  expect(changeLine({ number: 1, done: 2, total: 6, next_phase: "codegen" }, phases)).toBe("Change #1: step 3 of 6, next: Code generation");
});

test("Maintenance never says Start or Review: the open change, or nothing", () => {
  expect(maintenanceWord("draft", { number: 1, done: 1, total: 6, next_phase: "design" })).toBe("Step 2 of 6");
  expect(maintenanceWord("ready", null)).toBeNull();
  expect(maintenanceWord("draft", null)).toBeNull();
  expect(maintenanceWord("approved", null)).toBeNull();
  expect(maintenanceWord("stale", null)).toBe("Check");
  expect(maintenanceWord("locked", null)).toBe("Locked");
});

test("the answer of the analyst loses the lines the tracker shows", () => {
  const reply = "Change: Tasks get a priority.\nTouches REQ-001; 4 artifact(s) trace to REQ-001.\nPhases that move: Requirements, Design.\nCarry the change through with the button below: Wings updates one phase after the other.";
  expect(changeReplyText(reply)).toBe("Change: Tasks get a priority.\nTouches REQ-001; 4 artifact(s) trace to REQ-001.");
  expect(changeReplyText("Start the change with the button below.")).toBe("Start the change with the button below."); // never an empty message
});
