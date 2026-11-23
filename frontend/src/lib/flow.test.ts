import { describe, expect, it } from "vitest";
import type { PhaseInfo, PhaseState, PhaseStatus } from "../api/types";
import { acceptLabel, afterAccept, currentStep, programState, redoOf, screen, stepMark, stepTitle } from "./flow";

const IDS = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];
const REQUIRES: Record<string, string[]> = {
  requirements: [],
  design: ["requirements"],
  refinement: ["design"],
  codegen: ["refinement"],
  testing: ["codegen"],
  deployment: ["testing"],
  maintenance: ["deployment"],
};

function phases(statuses: Partial<Record<string, PhaseStatus>>, stale: Partial<Record<string, string>> = {}): PhaseState[] {
  const out: PhaseState[] = [];
  for (const id of IDS) {
    const status = statuses[id] ?? "locked";
    const can_run = REQUIRES[id].every((r) => out.find((p) => p.id === r)?.status === "approved");
    out.push({ id, title: id, status, requires: REQUIRES[id], implemented: true, can_run, updated_at: "", stale_cause: stale[id] ?? null });
  }
  return out;
}

const action = (name: string, required: string[] = []) => ({
  name,
  label: name,
  description: "",
  message_field: null,
  input_schema: { type: "object", properties: Object.fromEntries(required.map((r) => [r, { type: "string" }])), required },
});

const CATALOG = [
  { id: "requirements", actions: [action("start", ["description"]), action("answer", ["answers"]), action("revise", ["feedback"]), action("discuss", ["question"])] },
  { id: "design", actions: [action("generate"), action("revise", ["feedback"]), action("discuss", ["question"])] },
  { id: "refinement", actions: [action("review"), action("apply", ["findings"]), action("discuss", ["question"])] },
  { id: "codegen", actions: [action("generate"), action("revise", ["feedback"]), action("discuss", ["question"])] },
  { id: "testing", actions: [action("generate"), action("run"), action("probe"), action("explain"), action("discuss", ["question"])] },
  { id: "deployment", actions: [action("generate"), action("check"), action("revise", ["feedback"]), action("discuss", ["question"])] },
  { id: "maintenance", actions: [action("change", ["request"]), action("check"), action("discuss", ["question"])] },
] as unknown as PhaseInfo[];

const get = (ps: PhaseState[], id: string) => ps.find((p) => p.id === id)!;
const title = (id: string) => stepTitle({ id });

describe("step titles", () => {
  it("uses plain words for the steps", () => {
    expect(IDS.map(title)).toEqual(["Requirements", "Design", "Design review", "Code", "Tests", "Deployment", "Your program"]);
  });
});

describe("afterAccept and the Accept label", () => {
  it("starts the next step when it needs no input", () => {
    const ps = phases({ requirements: "draft" });
    const a = afterAccept(ps, [], "requirements", CATALOG);
    expect(a).toEqual({ kind: "make", phase: "design" });
    expect(acceptLabel(a, title)).toBe("Accept and draw the design");
  });

  it("redoes the next step that has to follow a change before anything else", () => {
    const ps = phases({ requirements: "draft", design: "stale", refinement: "stale", codegen: "stale" }, { design: "requirements" });
    const a = afterAccept(ps, ["design", "refinement", "codegen"], "requirements", CATALOG);
    expect(a).toEqual({ kind: "redo", phase: "design" });
    expect(acceptLabel(a, title)).toBe("Accept and redo Design");
  });

  it("finishes after the last build step", () => {
    const ps = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "approved", testing: "approved", deployment: "draft", maintenance: "ready" });
    const a = afterAccept(ps, [], "deployment", CATALOG);
    expect(a).toEqual({ kind: "done" });
    expect(acceptLabel(a, title)).toBe("Accept and finish");
  });

  it("opens a later step that already has a result instead of starting it again", () => {
    const ps = phases({ requirements: "draft", design: "draft" });
    expect(afterAccept(ps, [], "requirements", CATALOG)).toEqual({ kind: "open", phase: "design" });
  });
});

describe("screen", () => {
  it("asks for a description before anything exists", () => {
    const ps = phases({ requirements: "ready" });
    const s = screen({ phase: get(ps, "requirements"), all: ps, redo: [], catalog: CATALOG, hasResult: false });
    expect(s.marked?.text).toBe("Describe what you want to build.");
    expect(s.primary).toBeNull();
    expect(s.composer[0]).toBe("start");
  });

  it("opens on the conversation when the agent asks questions", () => {
    const ps = phases({ requirements: "needs_input" });
    const s = screen({ phase: get(ps, "requirements"), all: ps, redo: [], catalog: CATALOG, hasResult: false });
    expect(s.tab).toBe("conversation");
    expect(s.composer[0]).toBe("answer");
    expect(s.primary).toBeNull();
  });

  it("shows one Accept that says what comes next on a result", () => {
    const ps = phases({ requirements: "approved", design: "draft" });
    const s = screen({ phase: get(ps, "design"), all: ps, redo: [], catalog: CATALOG, hasResult: true });
    expect(s.tab).toBe("result");
    expect(s.primary).toMatchObject({ id: "accept", label: "Accept and review the design" });
    expect(s.marked?.tone).toBe("read");
    expect(s.composer[0]).toBe("revise");
  });

  it("puts a code check problem first and makes accepting a second choice", () => {
    const ps = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "draft" });
    const s = screen({ phase: get(ps, "codegen"), all: ps, redo: [], catalog: CATALOG, hasResult: true, check: { checked: true, in_sync: false, lines: ["a", "b"] } });
    expect(s.marked).toMatchObject({ tone: "problem", byCode: true, text: "The code differs from the class diagram in 2 places." });
    expect(s.primary?.id).toBe("fix_drift");
    expect(s.secondary.map((a) => a.label)).toContain("Accept anyway");
  });

  it("says how many tests fail and offers to explain them", () => {
    const ps = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "approved", testing: "draft" });
    const s = screen({ phase: get(ps, "testing"), all: ps, redo: [], catalog: CATALOG, hasResult: true, tests: { total: 9, failed: 2 } });
    expect(s.marked?.text).toBe("2 of 9 tests fail.");
    expect(s.primary?.id).toBe("explain");
  });

  it("offers to inject bugs before accepting green tests", () => {
    const ps = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "approved", testing: "draft" });
    const s = screen({ phase: get(ps, "testing"), all: ps, redo: [], catalog: CATALOG, hasResult: true, tests: { total: 9, failed: 0 }, canProbe: true });
    expect(s.marked).toMatchObject({ tone: "ok", text: "All 9 tests pass." });
    expect(s.primary?.id).toBe("accept");
    expect(s.secondary[0].id).toBe("probe");
  });

  it("never offers Accept on a step that needs a redo", () => {
    const ps = phases({ requirements: "approved", design: "stale", refinement: "stale" }, { design: "requirements", refinement: "requirements" });
    const s = screen({ phase: get(ps, "design"), all: ps, redo: ["design", "refinement"], catalog: CATALOG, hasResult: true });
    expect(s.marked?.tone).toBe("redo");
    expect(s.marked?.text).toContain("Requirements changed");
    expect(s.primary).toMatchObject({ id: "redo", label: "Redo Design" });
    expect([s.primary, ...s.secondary].some((a) => a?.id === "accept")).toBe(false);
    expect(s.secondary[0].id).toBe("keep");
  });

  it("sends a later step that needs a redo to the first one", () => {
    const ps = phases({ requirements: "approved", design: "stale", refinement: "stale" });
    const s = screen({ phase: get(ps, "refinement"), all: ps, redo: ["design", "refinement"], catalog: CATALOG, hasResult: true });
    expect(s.primary).toMatchObject({ id: "go", phase: "design" });
  });

  it("points an accepted step to the step the project waits on", () => {
    const ps = phases({ requirements: "approved", design: "draft" });
    const s = screen({ phase: get(ps, "requirements"), all: ps, redo: [], catalog: CATALOG, hasResult: true });
    expect(s.primary).toMatchObject({ id: "go", phase: "design", label: "Continue with Design" });
    expect(s.marked).toBeNull();
  });

  it("lets typing in Tests only ask questions, never write new tests (Ben, session s04)", () => {
    const ps = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "approved", testing: "draft" });
    const s = screen({ phase: get(ps, "testing"), all: ps, redo: [], catalog: CATALOG, hasResult: true, tests: { total: 3, failed: 0 } });
    expect(s.composer).toEqual(["discuss"]);
  });

  it("starts a step without input with one button", () => {
    const ps = phases({ requirements: "approved", design: "ready" });
    const s = screen({ phase: get(ps, "design"), all: ps, redo: [], catalog: CATALOG, hasResult: false });
    expect(s.primary).toMatchObject({ id: "start", label: "Draw the design", action: "generate" });
  });
});

describe("redo order with an open change", () => {
  const all = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "approved", testing: "approved", deployment: "approved", maintenance: "draft" });
  const progress = (states: Record<string, "done" | "current" | "waiting" | "untouched">, updated: string[] = []) => ({
    state: "open" as const,
    progress: {
      phases: Object.entries(states).map(([phase, state]) => ({ phase, title: phase, state, status: "approved" as const, updated: updated.includes(phase) })),
      current: null,
      started: false,
      complete: false,
      done: 0,
      total: 6,
    },
  });

  it("lists the steps a new change has not reached, before anything is stale (browser walk s07)", () => {
    const change = progress({ requirements: "current", design: "waiting", refinement: "waiting", codegen: "waiting", testing: "waiting", deployment: "waiting" });
    expect(redoOf({ phases: all, stale: [] }, change)).toEqual(["requirements", "design", "refinement", "codegen", "testing", "deployment"]);
  });

  it("drops a step the change already made again and merges the stale ones in pipeline order", () => {
    const ps = phases({ requirements: "draft", design: "stale", refinement: "stale" });
    const change = progress({ requirements: "current", design: "waiting", refinement: "waiting", codegen: "waiting" }, ["requirements"]);
    expect(redoOf({ phases: ps, stale: ["design", "refinement"] }, change)).toEqual(["design", "refinement", "codegen"]);
  });

  it("ignores a change that is complete", () => {
    expect(redoOf({ phases: all, stale: [] }, { ...progress({ requirements: "done" }), state: "complete" })).toEqual([]);
  });
});

describe("step marks and program state", () => {
  it("marks steps in words a person reads", () => {
    const ps = phases({ requirements: "approved", design: "stale", refinement: "draft" });
    expect(stepMark(get(ps, "requirements"), null, ["design"])).toBe("accepted");
    expect(stepMark(get(ps, "design"), null, ["design"])).toBe("redo");
    expect(stepMark(get(ps, "design"), "design", ["design"])).toBe("working");
    expect(stepMark(get(ps, "codegen"), null, [])).toBe("later");
  });

  it("knows the step the project waits on", () => {
    const ps = phases({ requirements: "approved", design: "stale", refinement: "stale" });
    expect(currentStep(ps, redoOf({ phases: ps }))?.id).toBe("design");
  });

  it("describes the program while it is built, redone and ready", () => {
    expect(programState(phases({ requirements: "approved", design: "draft" }), []).kind).toBe("building");
    expect(programState(phases({ requirements: "approved" }), ["design"]).text).toContain("1 step needs a redo: Design");
    const all = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "approved", testing: "approved", deployment: "approved", maintenance: "ready" });
    expect(programState(all, [])).toMatchObject({ kind: "ready", step: null });
  });
});
