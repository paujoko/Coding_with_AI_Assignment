import type { PhaseState } from "../api/types";
import type { UpdateRun } from "./catchup";
import { makeChange } from "./changes.fixture";
import { autoAdvanceTarget, nextCard, type NextInput, staleOf, updateLabel } from "./next";

const IDS = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];
const TITLES = ["Requirements", "Design", "Design refinement", "Code generation", "Testing", "Deployment", "Maintenance"];

const phases = (status: Partial<Record<string, PhaseState["status"]>> = {}, over: Partial<Record<string, Partial<PhaseState>>> = {}): PhaseState[] =>
  IDS.map((id, i) => ({
    id,
    title: TITLES[i],
    status: status[id] ?? (id === "maintenance" ? "ready" : "approved"),
    requires: i === 0 ? [] : [IDS[i - 1]],
    implemented: true,
    can_run: true,
    updated_at: "",
    stale_cause: null,
    ...over[id],
  }));

const card = (at: string, all: PhaseState[], over: Partial<NextInput> = {}) => {
  const phase = all.find((p) => p.id === at)!;
  return nextCard({ phase, all, stale: staleOf({ phases: all }), ...over });
};

const run = (over: Partial<UpdateRun> = {}): UpdateRun => ({
  active: false,
  only: false,
  total: 4,
  current: null,
  steps: [],
  stopping: false,
  stopped: null,
  stoppedPhase: null,
  failed: null,
  complete: false,
  ...over,
});

const fourStale = () =>
  phases({ design: "stale", refinement: "stale", codegen: "stale", testing: "stale" }, { design: { stale_cause: "requirements" } });

describe("out of date means Update, never Approve", () => {
  test("one out-of-date step: Update <name> is the primary, Keep as it is the quiet way out", () => {
    const all = phases({ design: "stale" }, { design: { stale_cause: "requirements" } });
    const c = card("design", all)!;
    expect(c).toMatchObject({ kind: "update", tone: "must", status: "stale", lead: "Design is out of date." });
    expect(c.text).toBe("Requirements changed after this was made.");
    expect(c.primary).toMatchObject({ id: "update", label: "Update Design" });
    expect(c.secondary.map((a) => a.id)).toEqual(["keep"]);
    expect(c.secondary[0].hint).toBe("The later steps may no longer match it.");
    expect([c.primary, ...c.secondary].some((a) => a?.id === "approve")).toBe(false);
  });

  test("several out of date, on the first: Update all N steps, Update this step only, Keep as it is", () => {
    const c = card("design", fourStale())!;
    expect(c.primary).toMatchObject({ id: "update", label: "Update all 4 steps" });
    expect(c.secondary.map((a) => [a.id, a.label])).toEqual([
      ["update_one", "Update this step only"],
      ["keep", "Keep as it is"],
    ]);
  });

  test("several out of date, on a later one: the first is where it starts, so the choice is to go there", () => {
    const c = card("codegen", fourStale())!;
    expect(c.primary?.label).toBe("Update all 4 steps");
    expect(c.secondary[0]).toMatchObject({ id: "go", label: "Go to Design", phase: "design" });
    expect(c.secondary.some((a) => a.id === "update_one")).toBe(false);
  });

  test("Keep as it is asks once more and says what it means", () => {
    const c = card("design", fourStale(), { keeping: true })!;
    expect(c).toMatchObject({ kind: "keep", lead: "Keep Design as it is?", text: "The later steps may no longer match it." });
    expect(c.primary).toMatchObject({ id: "keep_yes" });
    expect(c.secondary).toMatchObject([{ id: "keep_no" }]);
  });

  test("code that still matches the class diagram is said, as a result checked by code, and still offers Update", () => {
    const all = phases({ codegen: "stale", testing: "stale" }, { codegen: { stale_cause: "design" } });
    const c = card("codegen", all, { check: { checked: true, in_sync: true, diagram: "Domain classes" } })!;
    expect(c.text).toBe('Design changed. The code still matches the class diagram "Domain classes".');
    expect(c.byCode).toBe(true);
    expect(c.primary?.id).toBe("update");
  });

  test("code that differs is told as a count, not as the lines", () => {
    const all = phases({ codegen: "stale" }, { codegen: { stale_cause: "design" } });
    const c = card("codegen", all, { check: { checked: true, in_sync: false, diagram: "D", lines: ["a", "b", "c", "d"] } })!;
    expect(c.text).toBe("Design changed, and the code differs from the class diagram in 4 places.");
  });

  test("an out-of-date step behind an unfinished one sends you there first", () => {
    const all = phases({ design: "draft", refinement: "stale" }, { refinement: { can_run: false, stale_cause: "design" } });
    const c = card("refinement", all)!;
    expect(c).toMatchObject({ kind: "blocked", tone: "must" });
    expect(c.text).toBe("Design has to be done first.");
    expect(c.primary).toMatchObject({ id: "go", label: "Go to Design", phase: "design" });
  });

  test("an older backend without `stale` is read from the phase states", () => {
    expect(staleOf({ phases: fourStale() })).toEqual(["design", "refinement", "codegen", "testing"]);
    expect(staleOf({ phases: phases({ maintenance: "stale" }) })).toEqual([]); // Maintenance is never in the list
    expect(staleOf({ phases: phases(), stale: ["codegen"] })).toEqual(["codegen"]);
  });

  test("the update label", () => {
    const t = (id: string) => TITLES[IDS.indexOf(id)];
    expect(updateLabel(["design"], t)).toBe("Update Design");
    expect(updateLabel(["design", "codegen", "testing"], t)).toBe("Update all 3 steps");
  });
});

describe("a finished step with later steps out of date", () => {
  test("Requirements are done, four steps behind are out of date: the one thing to do is Update all", () => {
    const c = card("requirements", fourStale())!;
    expect(c).toMatchObject({ kind: "later_stale", tone: "must", lead: "4 steps are out of date." });
    expect(c.text).toBe("Design, Design refinement, Code generation, Testing");
    expect(c.primary?.label).toBe("Update all 4 steps");
  });
  test("one later step: Update <name>", () => {
    const c = card("requirements", phases({ deployment: "stale" }))!;
    expect(c.lead).toBe("1 step is out of date.");
    expect(c.primary?.label).toBe("Update Deployment");
  });
});

describe("an update in progress", () => {
  test("live progress, a Stop control, nothing else competes", () => {
    const u = run({ active: true, current: { phase: "codegen", title: "Code generation", index: 2, since: "" }, steps: [{ phase: "design", title: "Design", ran: [], approved: true, seconds: 1 }] });
    const c = card("design", fourStale(), { update: u })!;
    expect(c).toMatchObject({ kind: "updating", tone: "info", lead: "Updating Code generation...", text: "2 of 4", primary: null });
    expect(c.secondary).toMatchObject([{ id: "stop", label: "Stop" }]);
    expect(card("design", fourStale(), { update: { ...u, stopping: true } })!.secondary[0]).toMatchObject({ label: "Stops after this step", disabled: true });
  });
  test("a single step has no Stop", () => {
    const c = card("design", fourStale(), { update: run({ active: true, only: true, total: 1, current: { phase: "design", title: "Design", index: 1, since: "" } }) })!;
    expect(c.secondary).toEqual([]);
  });
});

describe("an update that stopped", () => {
  test("must read: the reason in plain words, and the way on", () => {
    const all = phases({ testing: "stale" });
    const u = run({ stopped: "Code generation: the checks failed. Open it and look at the failures.", stoppedPhase: "codegen" });
    const c = card("design", all, { update: u })!;
    expect(c).toMatchObject({ kind: "stopped", tone: "must", lead: "The update stopped." });
    expect(c.text).toBe("Code generation: the checks failed. Open it and look at the failures.");
    expect(c.primary).toMatchObject({ id: "go", label: "Open Code generation", phase: "codegen" });
    expect(c.secondary.map((a) => a.label)).toEqual(["Update again"]);
  });
  test("on the stopped step itself the way on is to update again", () => {
    const all = phases({ design: "stale", codegen: "stale" });
    const c = card("design", all, { update: run({ stopped: "You stopped the update after Design.", stoppedPhase: null }) })!;
    expect(c.primary?.label).toBe("Update all 2 steps");
  });
  test("a stop that nothing is waiting on any more is not repeated", () => {
    const c = card("design", phases(), { update: run({ stopped: "You stopped the update after Design.", stoppedPhase: null }) })!;
    expect(c.kind).toBe("done");
  });
  test("a refused request is the one red card, and offers to try again", () => {
    const c = card("design", fourStale(), { update: run({ failed: "An agent is already working on this project." }) })!;
    expect(c).toMatchObject({ kind: "error", status: "error", text: "An agent is already working on this project." });
    expect(c.primary?.label).toBe("Try again: update all 4 steps");
  });
  test("when the update finished, the card says what was updated", () => {
    const u = run({ complete: true, steps: [{ phase: "design", title: "Design", ran: [], approved: true, seconds: 1 }, { phase: "codegen", title: "Code generation", ran: [], approved: true, seconds: 1 }] });
    const c = card("design", phases(), { update: u })!;
    expect(c.text).toBe("Updated Design, Code generation.");
  });
});

describe("the other states of one step", () => {
  test("questions: must read, nothing to press", () => {
    const c = card("requirements", phases({ requirements: "needs_input" }))!;
    expect(c).toMatchObject({ kind: "answer", tone: "must", status: "needs_input", primary: null, lead: "Your answer is needed." });
  });
  test("ready for review: Approve is the one primary; Request changes and Inject bugs are quiet", () => {
    const c = card("testing", phases({ testing: "draft" }), { probe: { label: "Inject bugs" } })!;
    expect(c).toMatchObject({ kind: "review", tone: "info", status: "draft", primary: { id: "approve", label: "Approve" } });
    expect(c.secondary.map((a) => a.id)).toEqual(["probe", "request_changes"]);
  });
  test("ready for review while the code differs from the design: request changes leads, approve is explicitly anyway", () => {
    const c = card("codegen", phases({ codegen: "draft" }), { check: { checked: true, in_sync: false, diagram: "D", lines: ["x"] } })!;
    expect(c).toMatchObject({ kind: "review_drift", tone: "must", primary: { id: "request_changes" } });
    expect(c.text).toBe("The code differs from the class diagram in 1 place.");
    expect(c.secondary.map((a) => a.label)).toEqual(["Approve anyway"]);
  });
  test("asking for changes", () => {
    const c = card("design", phases({ design: "draft" }), { asking: true })!;
    expect(c).toMatchObject({ kind: "asking", primary: null });
    expect(c.secondary).toMatchObject([{ id: "cancel_request" }]);
  });
  test("done: go to the next step, Reopen is quiet", () => {
    const c = card("requirements", phases({ deployment: "draft" }))!;
    expect(c).toMatchObject({ kind: "done", text: "Next: Design.", primary: { id: "go", phase: "design" } });
    expect(c.secondary.map((a) => a.id)).toEqual(["reopen"]);
  });
  test("the whole project is done: Your project is ready, Run it first", () => {
    const c = card("deployment", phases(), { runIt: true })!;
    expect(c).toMatchObject({ kind: "ready_to_run", lead: "Your project is ready.", primary: { id: "run_it", label: "Run it" } });
    expect(c.secondary.map((a) => a.label)).toEqual(["Change something", "Reopen"]);
  });
  test("locked: info, and the way to the step before", () => {
    const all = phases({ design: "draft", refinement: "locked" }, { refinement: { can_run: false } });
    const c = card("refinement", all)!;
    expect(c).toMatchObject({ kind: "locked", tone: "info", text: "Approve Design first.", primary: { id: "go", phase: "design" } });
  });
  test("nothing made yet: one start button when no input is needed, else a line", () => {
    const all = phases({ design: "ready" });
    expect(card("design", all, { start: { action: "generate", label: "Generate design", needsInput: false } })!.primary).toMatchObject({ id: "start", action: "generate" });
    const c = card("requirements", phases({ requirements: "ready" }), { start: { action: "start", label: "Start", needsInput: true } })!;
    expect(c.primary).toBeNull();
    expect(c.text).toBe("Write below what you want, then send.");
  });
  test("a planned wing has no card", () => {
    const all = phases({ design: "locked" }, { design: { implemented: false, can_run: false } });
    expect(card("design", all)).toBeNull();
  });
});

describe("Maintenance", () => {
  const open = { number: 1, done: 1, total: 6, next_phase: "design" };
  test("at rest there is no card", () => {
    expect(card("maintenance", phases())).toBeNull();
    expect(card("maintenance", phases({ maintenance: "draft" }))).toBeNull(); // a result there is nothing to approve
  });
  test("an out-of-date consistency check offers the check", () => {
    const c = card("maintenance", phases({ maintenance: "stale" }), { rerun: { action: "check", label: "Check consistency" } })!;
    expect(c).toMatchObject({ kind: "check", primary: { id: "rerun", action: "check" } });
  });
  test("an open change with out-of-date steps: the same Update all card, with what the change still has to reach", () => {
    const change = makeChange(1);
    const all = phases({ design: "stale", refinement: "stale", codegen: "stale", testing: "stale", deployment: "stale", maintenance: "draft" });
    const c = card("maintenance", all, { openChange: open, changeNext: change.next, changeTodo: ["Design", "Design refinement"] })!;
    expect(c).toMatchObject({ kind: "change_update", tone: "must", text: "Still to update: Design, Design refinement." });
    expect(c.primary?.label).toBe("Update all 5 steps");
  });
  test("an open change that waits for an approval: approve it or look first", () => {
    const next = { ...makeChange(4).next!, kind: "approve" as const, steps: [] };
    const c = card("maintenance", phases({ maintenance: "draft" }), { openChange: open, changeNext: next })!;
    expect(c.kind).toBe("change_approve");
    expect(c.primary).toMatchObject({ id: "approve_change", label: "Approve the tests" });
    expect(c.secondary).toMatchObject([{ id: "go", label: "Look at the tests", phase: "testing" }]);
  });
  test("an open change blocked by questions or failed checks: must read, with the reason", () => {
    const next = { ...makeChange(4).next!, kind: "blocked" as const, steps: [], reason: "Some tests do not pass. Fix the code or the tests." };
    const c = card("maintenance", phases({ maintenance: "draft" }), { openChange: open, changeNext: next })!;
    expect(c).toMatchObject({ kind: "change_input", tone: "must", text: "Some tests do not pass. Fix the code or the tests.", primary: { id: "go", label: "Open Testing" } });
  });
  test("an open change with nothing out of date yet: one step of the change", () => {
    const c = card("maintenance", phases({ maintenance: "draft" }), { openChange: open, changeNext: makeChange(1).next, changeTodo: ["Design"] })!;
    expect(c.kind).toBe("change_step");
    expect(c.primary).toMatchObject({ id: "advance_change", label: "Update the design" });
  });
  test("an update running inside a change shows the same progress card", () => {
    const u = run({ active: true, total: 5, current: { phase: "design", title: "Design", index: 1, since: "" } });
    expect(card("maintenance", phases({ maintenance: "draft", design: "stale" }), { openChange: open, update: u })!.kind).toBe("updating");
  });
});

describe("going on by itself", () => {
  test("after an approval the next step opens when it is ready to start", () => {
    expect(autoAdvanceTarget(phases({ design: "ready" }), "requirements")).toBe("design");
  });
  test("not when the next step is out of date, has output, or the project is ready to run", () => {
    expect(autoAdvanceTarget(phases({ design: "stale" }), "requirements")).toBeNull();
    expect(autoAdvanceTarget(phases({ design: "draft" }), "requirements")).toBeNull();
    expect(autoAdvanceTarget(phases(), "deployment")).toBeNull();
    expect(autoAdvanceTarget(phases({ maintenance: "ready" }), "maintenance")).toBeNull();
  });
});
