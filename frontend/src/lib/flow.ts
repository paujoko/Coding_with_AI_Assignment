import type { Change, DesignCheck, PhaseInfo, PhaseState, Project } from "../api/types";

// The guided flow (docs/superpowers/specs/2026-11-23-guided-flow-design.md): one loop for building and for changing.
// At every step the developer looks at what Wings made, then accepts it or says what to change. Accept starts the
// next step. A change to an accepted step marks the later ones for a redo, and the redo runs through the same loop.
//
// Everything here is a pure function of what the backend reports. The screen draws what it returns and nothing else
// decides which button is the primary one.

/** Step names in plain words. The backend's titles stay in the API. */
export const STEP_TITLE: Record<string, string> = {
  requirements: "Requirements",
  design: "Design",
  refinement: "Design review",
  codegen: "Code",
  testing: "Tests",
  deployment: "Deployment",
  maintenance: "Your program",
};

export const stepTitle = (p: { id: string; title?: string }) => STEP_TITLE[p.id] ?? p.title ?? p.id;

/** What starting the step does, after "Accept and ...". */
const MAKE: Record<string, string> = {
  requirements: "write the requirements",
  design: "draw the design",
  refinement: "review the design",
  codegen: "write the code",
  testing: "write and run the tests",
  deployment: "prepare the deployment",
};

const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const makeLabel = (id: string) => capital(MAKE[id] ?? `start ${id}`);

/** What a person checks in a result, one sentence per step. */
const CHECK: Record<string, string> = {
  requirements: "Check that the requirements describe what you want.",
  design: "Check that the diagrams cover every requirement.",
  refinement: "Read the review. Accept when the design is good enough.",
  codegen: "Look through the code, then accept it.",
  testing: "Check the test results, then accept them.",
  deployment: "Check the deployment files, then accept them.",
};

/** The steps that build the program, in order. Your program (Maintenance) comes after them. */
export const buildSteps = <T extends Pick<PhaseState, "id" | "implemented">>(phases: T[]): T[] =>
  phases.filter((p) => p.implemented && p.id !== "maintenance");

/** The phase ids that need a redo, in pipeline order: the backend's `stale` (API 10, else computed from the states),
 * plus the steps an open change still has to reach (a change from Your program starts before anything is stale).
 * A step the change already made again and that waits for Accept is not a redo. */
export function redoOf(p: Pick<Project, "phases" | "stale">, change?: Pick<Change, "state" | "progress"> | null): string[] {
  const stale = Array.isArray(p.stale)
    ? p.stale
    : buildSteps(p.phases)
        .filter((x) => x.status === "stale")
        .map((x) => x.id);
  if (!change || change.state !== "open") return stale;
  const status = (id: string) => p.phases.find((x) => x.id === id)?.status;
  const pending = change.progress.phases
    .filter((x) => x.state === "waiting" || (x.state === "current" && !x.updated && status(x.phase) === "approved"))
    .map((x) => x.phase);
  const all = new Set([...stale, ...pending]);
  return buildSteps(p.phases)
    .map((x) => x.id)
    .filter((id) => all.has(id));
}

export type Mark = "accepted" | "yours" | "redo" | "working" | "later";

/** The mark of a step in the step list. */
export function stepMark(p: PhaseState, running: string | null, redo: string[]): Mark {
  if (running === p.id) return "working";
  if (redo.includes(p.id) || p.status === "stale") return "redo";
  if (p.status === "approved") return "accepted";
  if (p.can_run && (p.status === "needs_input" || p.status === "draft" || p.status === "ready")) return "yours";
  return "later";
}

export const MARK_WORD: Record<Mark, string> = {
  accepted: "Accepted",
  yours: "Your turn",
  redo: "Redo",
  working: "Working",
  later: "Later",
};

/** All build steps accepted and nothing to redo. */
export const finished = (phases: PhaseState[], redo: string[]) =>
  redo.length === 0 && buildSteps(phases).length > 0 && buildSteps(phases).every((p) => p.status === "approved");

/** The step the project waits on: the first build step not accepted. After a change that is the changed step
 * (waiting for Accept) before the first one to redo, because the redo builds on it. */
export function currentStep(phases: PhaseState[], redo: string[]): PhaseState | null {
  return buildSteps(phases).find((p) => p.status !== "approved" || redo.includes(p.id)) ?? null;
}

/** A step's generator that runs without any input (Draw the design, Write the code, ...), if it has one. */
export function autoStart(info: PhaseInfo | undefined): string | null {
  const first = info?.actions[0];
  if (!first) return null;
  return (first.input_schema.required ?? []).length === 0 ? first.name : null;
}

/** A deterministic action that belongs right after a step's generator: Tests are run as soon as they are written. */
export const FOLLOW_UP: Record<string, string> = { testing: "run" };

/** What Accept leads to, decided before it is pressed so the button can say it. */
export type AfterAccept =
  | { kind: "redo"; phase: string } // the next step that has to follow the change
  | { kind: "make"; phase: string } // the next step, started at once
  | { kind: "open"; phase: string } // the next step needs the developer first
  | { kind: "done" }; // everything is accepted: Your program

export function afterAccept(phases: PhaseState[], redo: string[], acceptedId: string, catalog: PhaseInfo[]): AfterAccept {
  const later = redo.filter((id) => id !== acceptedId);
  if (later.length) return { kind: "redo", phase: later[0] };
  const steps = buildSteps(phases);
  const i = steps.findIndex((p) => p.id === acceptedId);
  const next = steps.slice(i + 1).find((p) => p.status !== "approved");
  if (!next) {
    const open = steps.find((p) => p.id !== acceptedId && p.status !== "approved");
    return open ? { kind: "open", phase: open.id } : { kind: "done" };
  }
  const startable = next.status === "ready" || next.status === "locked"; // locked only because this step was not accepted yet
  return startable && autoStart(catalog.find((c) => c.id === next.id)) ? { kind: "make", phase: next.id } : { kind: "open", phase: next.id };
}

export function acceptLabel(after: AfterAccept, title: (id: string) => string): string {
  switch (after.kind) {
    case "redo":
      return `Accept and redo ${title(after.phase)}`;
    case "make":
      return `Accept and ${MAKE[after.phase] ?? `start ${title(after.phase)}`}`;
    case "open":
      return `Accept and go to ${title(after.phase)}`;
    case "done":
      return "Accept and finish";
  }
}

// ---------- One step's screen ----------

export type ActId =
  | "accept" // approve, then whatever afterAccept says
  | "start" // run the step's generator
  | "redo" // catch-up without approval: this step is made again and waits for Accept
  | "keep" // accept a step that needs a redo without making it again (asks once)
  | "go" // open `phase`
  | "fix_drift" // Code: revise so the code follows the class diagram
  | "explain" // Tests: explain the failures
  | "probe" // Tests: inject bugs
  | "rerun" // Deployment: check again
  | "apply" // Design review: apply the findings the developer ticked
  | "send_answers"; // the agent asked questions: send the picked answers

export interface Act {
  id: ActId;
  label: string;
  phase?: string;
  action?: string;
  hint?: string;
}

/** The one sentence a screen marks as must-read. tone: read (what to check), problem (something failed), redo, ok (a pass checked by code). */
export interface Marked {
  text: string;
  tone: "read" | "problem" | "redo" | "ok";
  byCode?: boolean;
  details?: string[]; // the lines behind it, shown under the sentence (e.g. where code and diagram differ)
}

export interface Screen {
  tab: "result" | "conversation"; // what the screen opens on
  marked: Marked | null;
  primary: Act | null;
  secondary: Act[];
  composer: string[]; // the actions the text box offers, default first; empty: no text box
  placeholder: string;
}

export interface ScreenInput {
  phase: PhaseState;
  all: PhaseState[];
  redo: string[];
  catalog: PhaseInfo[];
  hasResult: boolean;
  check?: DesignCheck | null; // Code: the code against the class diagram, checked by code
  tests?: { total: number; failed: number } | null; // Tests: the latest run
  deploy?: { passed: boolean } | null; // Deployment: the latest check
  openFindings?: number; // Design review: findings not applied yet
  canProbe?: boolean; // Tests: green and current, bugs not injected yet
  strength?: { caught: number; judged: number } | null; // Tests: the latest injected bugs, while current
  pickedFindings?: number; // Design review: open findings the developer ticked
  answers?: { picked: number; asked: number }; // questions answered on the cards, and how many were asked
}

const MESSAGE_ACTIONS = ["answer", "start", "revise", "change", "discuss"];

/** The text box's actions for a state, default first. Design review changes through its findings. Tests: a question by
 * default; "Change the tests" writes them again with the developer's guidance (named so, never the default: session s04). */
function composerFor(actions: string[], state: PhaseState["status"], phase: string): string[] {
  const has = (n: string) => actions.includes(n);
  if (phase === "testing" && state !== "ready") return ["discuss", "generate"].filter(has);
  const order = state === "needs_input" ? ["answer", "discuss"] : state === "ready" ? ["start", "discuss"] : ["revise", "change", "discuss"];
  return order.filter((n) => has(n) && MESSAGE_ACTIONS.includes(n));
}

export function screen(i: ScreenInput): Screen {
  const { phase, all, redo, catalog } = i;
  const info = catalog.find((c) => c.id === phase.id);
  const actions = info?.actions.map((a) => a.name) ?? [];
  const title = (id: string) => stepTitle(all.find((p) => p.id === id) ?? { id });
  const composer = composerFor(actions, phase.status, phase.id);
  const base = { composer, placeholder: "Say what to change in this step" };

  // Not yet: an earlier step has to be accepted (or redone) first.
  if (!phase.can_run) {
    const blocker = all.find((x) => phase.requires.includes(x.id) && x.status !== "approved");
    const first = redo[0] && redo[0] !== phase.id ? redo[0] : blocker?.id;
    return {
      tab: i.hasResult ? "result" : "conversation",
      marked: first ? { text: `${redo.includes(phase.id) ? "This step will be redone" : "This step comes"} after ${title(first)}.`, tone: "read" } : null,
      primary: first ? { id: "go", label: `Go to ${title(first)}`, phase: first } : null,
      secondary: [],
      composer: [],
      placeholder: "",
    };
  }

  if (phase.status === "needs_input") {
    return {
      tab: "conversation",
      marked: { text: "Answer the questions so Wings can go on.", tone: "read" },
      primary:
        i.answers && i.answers.picked > 0
          ? { id: "send_answers", label: i.answers.picked < i.answers.asked ? `Send ${i.answers.picked} of ${i.answers.asked} answers` : "Send the answers" }
          : null,
      secondary: [],
      composer,
      placeholder: "Your answers",
    };
  }

  if (phase.status === "stale" || redo.includes(phase.id)) {
    const mine = redo[0] === phase.id || redo.length === 0;
    const text = phase.stale_cause
      ? `${title(phase.stale_cause)} changed after this was made. Redo this step so it follows.`
      : "Your change reaches this step. Redo it so it follows the change.";
    return {
      ...base,
      tab: "result",
      marked: { text, tone: "redo" },
      primary: mine ? { id: "redo", label: `Redo ${title(phase.id)}` } : { id: "go", label: `Go to ${title(redo[0])}`, phase: redo[0] },
      secondary: [{ id: "keep", label: "Keep it unchanged", hint: "Accepts the step as it is. Later steps may then not match it." }],
    };
  }

  if (phase.status === "ready" && !i.hasResult) {
    const auto = autoStart(info);
    return {
      tab: "conversation",
      marked: auto ? null : { text: "Describe what you want to build.", tone: "read" },
      primary: auto ? { id: "start", label: makeLabel(phase.id), action: auto } : null,
      secondary: [],
      composer: auto ? composer.filter((n) => n === "discuss") : composer,
      placeholder: auto ? "Ask a question" : "What should the program do?",
    };
  }

  const accept: Act = { id: "accept", label: acceptLabel(afterAccept(all, redo, phase.id, catalog), title) };

  if (phase.status === "draft") {
    let marked: Marked = { text: CHECK[phase.id] ?? "Check the result, then accept it.", tone: "read" };
    let primary: Act = accept;
    const secondary: Act[] = [];
    const anyway: Act = { ...accept, label: "Accept anyway" };
    if (phase.id === "codegen" && i.check?.checked) {
      if (i.check.in_sync === false) {
        const k = i.check.lines?.length ?? 0;
        marked = { text: `The code differs from the class diagram in ${k} ${k === 1 ? "place" : "places"}.`, tone: "problem", byCode: true, details: i.check.lines ?? [] };
        if (actions.includes("revise")) {
          primary = { id: "fix_drift", label: "Make the code follow the diagram" };
          secondary.push(anyway);
        }
      } else if (i.check.in_sync === true) {
        marked = { text: "The code matches the class diagram. Look through it, then accept it.", tone: "ok", byCode: true };
      }
    }
    if (phase.id === "testing" && !i.tests && actions.includes("run")) {
      marked = { text: "The tests are written but have not run yet.", tone: "read" };
      primary = { id: "rerun", label: "Run the tests", action: "run" };
    }
    if (phase.id === "testing" && i.tests) {
      const { total, failed } = i.tests;
      if (failed > 0) {
        marked = { text: `${failed} of ${total} ${total === 1 ? "test fails" : "tests fail"}.`, tone: "problem", byCode: true };
        if (actions.includes("explain")) {
          primary = { id: "explain", label: "Explain the failures", action: "explain" };
          secondary.push(anyway);
        }
      } else {
        const s = i.strength;
        const caught = s && s.judged > 0 ? ` They caught ${s.caught} of ${s.judged} injected bugs.` : "";
        marked = { text: `All ${total} ${total === 1 ? "test passes" : "tests pass"}.${caught}`, tone: "ok", byCode: true };
        if (i.canProbe) secondary.push({ id: "probe", label: "Inject bugs first", action: "probe", hint: "Wings changes one line of the code at a time and runs the tests against each change. No model is asked." });
      }
    }
    if (phase.id === "deployment" && i.deploy) {
      if (!i.deploy.passed) {
        marked = { text: "The deployment check failed.", tone: "problem", byCode: true };
        if (actions.includes("check")) {
          primary = { id: "rerun", label: "Check again", action: "check" };
          secondary.push(anyway);
        }
      } else {
        marked = { text: "The deployment check started your program.", tone: "ok", byCode: true };
      }
    }
    if (phase.id === "refinement" && (i.openFindings ?? 0) > 0) {
      const n = i.pickedFindings ?? 0;
      if (n > 0) {
        // A ticked finding is not applied by Accept: say so and make applying the obvious move (walk s07b).
        marked = { text: `You ticked ${n} ${n === 1 ? "finding" : "findings"}. Apply ${n === 1 ? "it" : "them"}, or untick ${n === 1 ? "it" : "them"} to accept the design as it is.`, tone: "read" };
        primary = { id: "apply", label: `Apply ${n} ${n === 1 ? "finding" : "findings"}` };
        secondary.push({ ...accept, label: "Accept without applying" });
      } else {
        marked = { text: "Tick the findings you agree with and apply them, or accept the design as it is.", tone: "read" };
      }
    }
    return { ...base, tab: "result", marked, primary, secondary };
  }

  // Accepted. The way on is the step the project waits on, or Your program.
  const waiting = currentStep(all, redo);
  const secondary: Act[] = phase.id === "testing" && i.canProbe ? [{ id: "probe", label: "Inject bugs", action: "probe" }] : [];
  const primary: Act | null =
    waiting && waiting.id !== phase.id
      ? { id: "go", label: `Continue with ${title(waiting.id)}`, phase: waiting.id }
      : !waiting
        ? { id: "go", label: "Open your program", phase: "maintenance" }
        : null;
  return { ...base, tab: "result", marked: null, primary, secondary };
}

// ---------- Your program ----------

export interface ProgramState {
  kind: "building" | "redo" | "ready";
  text: string;
  step: string | null; // the step to open
}

export function programState(phases: PhaseState[], redo: string[]): ProgramState {
  const steps = buildSteps(phases);
  const title = (id: string) => stepTitle(phases.find((p) => p.id === id) ?? { id });
  if (redo.length) {
    return {
      kind: "redo",
      text: `Your change is not through yet. ${redo.length === 1 ? "1 step needs" : `${redo.length} steps need`} a redo: ${redo.map(title).join(", ")}.`,
      step: currentStep(phases, redo)?.id ?? redo[0],
    };
  }
  const open = steps.find((p) => p.status !== "approved");
  if (open) {
    const done = steps.filter((p) => p.status === "approved").length;
    return { kind: "building", text: `Being built: ${done} of ${steps.length} steps accepted. Next: ${title(open.id)}.`, step: open.id };
  }
  return { kind: "ready", text: `Ready. All ${steps.length} steps accepted.`, step: null };
}
