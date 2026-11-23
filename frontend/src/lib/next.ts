import type { ChangeNext, DesignCheck, OpenChange, PhaseState, Project } from "../api/types";
import type { IconName } from "../components/Icon";
import type { UpdateRun } from "./catchup";
import { phaseObject } from "./changes";
import { readyToRun, statusHint } from "./status";

// The one next step, in one place: the card above the input. A pure function from what the project knows to
// {a status line, one primary button, quiet secondary choices}. Nothing here touches the backend.
//
// Reading hierarchy (docs/code/design.md): tone "must" is something the developer has to read now (a question, an
// out-of-date step, an error, an update that stopped); tone "info" is the way on when nothing is wrong.
// Rule: an out-of-date step never offers plain Approve. It offers Update; "Keep as it is" is a quiet second click.

export type Tone = "must" | "info";

export type ActId =
  | "approve" // approve this phase
  | "update" // POST /catch-up in a loop: every step that is out of date
  | "update_one" // POST /catch-up once
  | "keep" // ask whether to keep an out-of-date step as it is
  | "keep_yes" // approve the out-of-date step after all
  | "keep_no"
  | "go" // open `phase`
  | "reopen"
  | "request_changes"
  | "cancel_request"
  | "rerun" // run the phase's deterministic action (Run tests, Check again)
  | "probe" // Inject bugs
  | "run_it"
  | "stop" // stop the update after the running step
  | "start" // run the phase's first action
  | "approve_change" // approve the phase a change waits at (change advance)
  | "advance_change"; // one step of the open change (change advance, no approval)

export interface NextAct {
  id: ActId;
  label: string;
  phase?: string;
  action?: string;
  hint?: string; // tooltip: what pressing it means
  disabled?: boolean;
}

export type NextKind =
  | "updating"
  | "stopped"
  | "error"
  | "change_input"
  | "change_approve"
  | "change_update"
  | "change_step"
  | "blocked"
  | "locked"
  | "answer"
  | "keep"
  | "update"
  | "review"
  | "review_drift"
  | "asking"
  | "later_stale"
  | "ready_to_run"
  | "done"
  | "start"
  | "check"
  | "none";

export interface NextCard {
  kind: NextKind;
  tone: Tone;
  status: "needs_input" | "stale" | "draft" | "approved" | "locked" | "running" | "error" | "ready";
  icon: IconName;
  lead: string; // the status line, bold
  text: string; // one short sentence, may be empty
  byCode?: boolean; // the sentence is a result computed by code: show the "Checked by code" label
  primary: NextAct | null;
  secondary: NextAct[];
}

export interface NextInput {
  phase: PhaseState;
  all: PhaseState[];
  stale: string[]; // phase ids that are out of date, pipeline order, Maintenance excluded
  openChange?: OpenChange | null;
  changeNext?: ChangeNext | null; // what the open change waits for
  changeTodo?: string[]; // titles of the phases the open change still has to reach
  check?: DesignCheck | null; // code generation: the code against the class diagram
  update?: UpdateRun | null; // the last or running "Update all"
  carryFailed?: string | null; // a refused change step
  asking?: boolean; // the developer pressed Request changes and should now type
  keeping?: boolean; // the developer pressed "Keep as it is" and is asked to confirm
  start?: { action: string; label: string; needsInput: boolean } | null; // the phase's first action
  rerun?: { action: string; label: string } | null;
  probe?: { label: string } | null; // Testing with a green run: inject bugs before approving
  runIt?: boolean; // the program can be started and its commands are there
}

/** The phase ids that are out of date: the backend's `stale` (API 10), else computed from the phase states. */
export function staleOf(p: Pick<Project, "phases" | "stale">): string[] {
  if (Array.isArray(p.stale)) return p.stale;
  return p.phases.filter((x) => x.implemented && x.id !== "maintenance" && x.status === "stale").map((x) => x.id);
}

/** "Update all 4 steps", or "Update Design" when there is one. */
export const updateLabel = (stale: string[], title: (id: string) => string): string =>
  stale.length > 1 ? `Update all ${stale.length} steps` : `Update ${title(stale[0])}`;

/** After an approval: the phase to open by itself, when exactly one next step is waiting to be started. */
export function autoAdvanceTarget(phases: PhaseState[], approvedId: string): string | null {
  if (approvedId === "maintenance" || readyToRun(phases)) return null;
  const i = phases.findIndex((p) => p.id === approvedId);
  const next = phases.slice(i + 1).find((p) => p.implemented && p.can_run);
  return next && next.status === "ready" && next.id !== "maintenance" ? next.id : null;
}

const KEEP_HINT = "The later steps may no longer match it.";

export function nextCard(i: NextInput): NextCard | null {
  const { phase, all } = i;
  const title = (id: string) => all.find((p) => p.id === id)?.title ?? id;
  const u = i.update ?? null;
  const n = i.stale.length;
  const updateAct = (): NextAct => ({ id: "update", label: updateLabel(i.stale, title), hint: n > 1 ? "Runs each step in order and approves it when its code checks pass." : undefined });
  const isMaintenance = phase.id === "maintenance";

  // 1. An update is running.
  if (u?.active) {
    const cur = u.current;
    return {
      kind: "updating",
      tone: "info",
      status: "running",
      icon: "spinner",
      lead: cur ? `Updating ${cur.title}...` : "Updating...",
      text: `${cur?.index ?? u.steps.length + 1} of ${Math.max(u.total, 1)}`,
      primary: null,
      secondary: u.only ? [] : [{ id: "stop", label: u.stopping ? "Stops after this step" : "Stop", disabled: u.stopping }],
    };
  }

  // 2. A refused request (409, backend unreachable): the only red card.
  const failed = u?.failed ?? i.carryFailed ?? null;
  if (failed) {
    return {
      kind: "error",
      tone: "must",
      status: "error",
      icon: "alert",
      lead: "That did not run.",
      text: failed,
      primary: n > 0 ? { id: "update", label: n > 1 ? `Try again: update all ${n} steps` : `Try again: update ${title(i.stale[0])}` } : null,
      secondary: [],
    };
  }

  // 3. An update stopped and something is still open: say why and how to go on.
  if (u && !u.active && u.stopped) {
    const at = u.stoppedPhase;
    const unresolved = n > 0 || (at !== null && all.find((p) => p.id === at)?.status !== "approved");
    if (unresolved) {
      const away = at !== null && at !== phase.id ? at : null;
      return {
        kind: "stopped",
        tone: "must",
        status: "stale",
        icon: "alert",
        lead: "The update stopped.",
        text: u.stopped,
        primary: away ? { id: "go", label: `Open ${title(away)}`, phase: away } : n > 0 ? updateAct() : null,
        secondary: away && n > 0 ? [{ id: "update", label: "Update again" }] : [],
      };
    }
  }

  // 4. Maintenance with a change in progress: the same card, the same buttons.
  if (isMaintenance && i.openChange) {
    const next = i.changeNext ?? null;
    if (next && (next.kind === "input" || next.kind === "blocked")) {
      return {
        kind: "change_input",
        tone: "must",
        status: "needs_input",
        icon: "alert",
        lead: "Your change needs you.",
        text: next.reason ?? `${next.title} needs you.`,
        primary: { id: "go", label: `Open ${next.title}`, phase: next.phase },
        secondary: [],
      };
    }
    if (next?.kind === "approve") {
      const what = phaseObject(next.phase, next.title);
      return {
        kind: "change_approve",
        tone: "info",
        status: "draft",
        icon: "sparkle",
        lead: `${next.title} is ready for review.`,
        text: "Check it, then approve it.",
        primary: { id: "approve_change", label: `Approve ${what}`, phase: next.phase },
        secondary: [{ id: "go", label: `Look at ${what}`, phase: next.phase }],
      };
    }
    const todo = (i.changeTodo ?? []).join(", ");
    if (n > 0) {
      return {
        kind: "change_update",
        tone: "must",
        status: "stale",
        icon: "refresh",
        lead: "Your project has to follow this change.",
        text: todo ? `Still to update: ${todo}.` : "",
        primary: updateAct(),
        secondary: [],
      };
    }
    if (next) {
      return {
        kind: "change_step",
        tone: "info",
        status: "stale",
        icon: "refresh",
        lead: "Your project has to follow this change.",
        text: todo ? `Still to update: ${todo}.` : "",
        primary: { id: "advance_change", label: `Update ${phaseObject(next.phase, next.title)}`, phase: next.phase },
        secondary: [],
      };
    }
  }

  // 5. The step cannot be worked on yet.
  if (!phase.can_run) {
    const blocker = all.find((x) => phase.requires.includes(x.id) && x.status !== "approved");
    const go: NextAct | null = blocker ? { id: "go", label: `Go to ${blocker.title}`, phase: blocker.id } : null;
    if (phase.status === "stale")
      return {
        kind: "blocked",
        tone: "must",
        status: "stale",
        icon: "alert",
        lead: `${phase.title} is out of date.`,
        text: blocker ? `${blocker.title} has to be done first.` : statusHint(phase, all),
        primary: go,
        secondary: [],
      };
    if (!phase.implemented) return null;
    return { kind: "locked", tone: "info", status: "locked", icon: "lock", lead: "Not yet.", text: statusHint(phase, all), primary: go, secondary: [] };
  }

  // 6. The agent asked questions.
  if (phase.status === "needs_input") {
    return {
      kind: "answer",
      tone: "must",
      status: "needs_input",
      icon: "alert",
      lead: "Your answer is needed.",
      text: "Pick an option for each question, then send.",
      primary: null,
      secondary: [],
    };
  }

  // 7. Out of date: Update, never Approve.
  if (phase.status === "stale") {
    if (isMaintenance) {
      return {
        kind: "check",
        tone: "must",
        status: "stale",
        icon: "alert",
        lead: "The consistency check is out of date.",
        text: "",
        primary: i.rerun ? { id: "rerun", label: i.rerun.label, action: i.rerun.action } : null,
        secondary: [],
      };
    }
    const first = i.stale[0];
    const mine = i.stale.includes(phase.id);
    if (i.keeping) {
      return {
        kind: "keep",
        tone: "must",
        status: "stale",
        icon: "alert",
        lead: `Keep ${phase.title} as it is?`,
        text: KEEP_HINT,
        primary: { id: "keep_yes", label: "Yes, keep it" },
        secondary: [{ id: "keep_no", label: "Cancel" }],
      };
    }
    const cause = phase.stale_cause ? title(phase.stale_cause) : "An earlier step";
    const check = i.check?.checked ? i.check : null;
    let text = `${cause} changed after this was made.`;
    let byCode = false;
    if (check?.in_sync === true) {
      text = `${cause} changed. The code still matches the class diagram "${check.diagram}".`;
      byCode = true;
    } else if (check?.in_sync === false) {
      const k = check.lines?.length ?? 0;
      text = `${cause} changed, and the code differs from the class diagram in ${k} ${k === 1 ? "place" : "places"}.`;
      byCode = true;
    }
    const keep: NextAct = { id: "keep", label: "Keep as it is", hint: KEEP_HINT };
    const secondary: NextAct[] = [];
    if (n > 1) {
      if (mine && first === phase.id) secondary.push({ id: "update_one", label: "Update this step only" });
      else if (first) secondary.push({ id: "go", label: `Go to ${title(first)}`, phase: first });
    }
    secondary.push(keep);
    return {
      kind: "update",
      tone: "must",
      status: "stale",
      icon: "alert",
      lead: `${phase.title} is out of date.`,
      text,
      byCode,
      primary: n > 0 ? updateAct() : { id: "update", label: `Update ${phase.title}` },
      secondary,
    };
  }

  // 8. Ready for review (Maintenance results are nothing to approve).
  if (phase.status === "draft" && !isMaintenance) {
    if (i.asking) {
      return {
        kind: "asking",
        tone: "info",
        status: "draft",
        icon: "pencil",
        lead: "Say what should change.",
        text: "Write it below, then send.",
        primary: null,
        secondary: [{ id: "cancel_request", label: "Cancel" }],
      };
    }
    const probe: NextAct[] = i.probe ? [{ id: "probe", label: i.probe.label, hint: "Wings changes one line of the code at a time and runs the tests against each change." }] : [];
    const check = i.check?.checked ? i.check : null;
    if (check?.in_sync === false) {
      const k = check.lines?.length ?? 0;
      return {
        kind: "review_drift",
        tone: "must",
        status: "draft",
        icon: "alert",
        lead: `${phase.title} is ready for review.`,
        text: `The code differs from the class diagram in ${k} ${k === 1 ? "place" : "places"}.`,
        byCode: true,
        primary: { id: "request_changes", label: "Request changes" },
        secondary: [...probe, { id: "approve", label: "Approve anyway" }],
      };
    }
    return {
      kind: "review",
      tone: "info",
      status: "draft",
      icon: "sparkle",
      lead: `${phase.title} is ready for review.`,
      text: "Check the results, then approve.",
      primary: { id: "approve", label: "Approve" },
      secondary: [...probe, { id: "request_changes", label: "Request changes" }],
    };
  }

  // 9. Done, or Maintenance at rest. Steps behind this one that are out of date come first.
  if (phase.status === "approved" || isMaintenance) {
    if (n > 0 && !i.stale.includes(phase.id)) {
      const names = i.stale.map(title).join(", ");
      return {
        kind: "later_stale",
        tone: "must",
        status: "stale",
        icon: "alert",
        lead: n === 1 ? "1 step is out of date." : `${n} steps are out of date.`,
        text: names,
        primary: updateAct(),
        secondary: [],
      };
    }
    if (isMaintenance) return null;
    const updated = u && !u.active && u.complete && u.steps.length > 0 ? `Updated ${u.steps.map((s) => s.title).join(", ")}.` : "";
    const reopen: NextAct = { id: "reopen", label: "Reopen" };
    if (i.runIt) {
      const last = phase.id === "deployment";
      return {
        kind: "ready_to_run",
        tone: "info",
        status: "approved",
        icon: "check",
        lead: last ? "Your project is ready." : `${phase.title} is done. The project is ready to run.`,
        text: updated || (last ? "Run it to try it out." : ""),
        primary: { id: "run_it", label: "Run it" },
        secondary: last ? [{ id: "go", label: "Change something", phase: "maintenance" }, reopen] : [reopen],
      };
    }
    const next = all.slice(all.findIndex((x) => x.id === phase.id) + 1).find((x) => x.can_run);
    return {
      kind: "done",
      tone: "info",
      status: "approved",
      icon: "check",
      lead: `${phase.title} is done.`,
      text: updated || (next ? `Next: ${next.title}.` : ""),
      primary: next ? { id: "go", label: `Go to ${next.title}`, phase: next.id } : null,
      secondary: [reopen],
    };
  }

  // 10. Nothing made yet.
  if (phase.status === "ready" && i.start) {
    return {
      kind: "start",
      tone: "info",
      status: "ready",
      icon: "sparkle",
      lead: i.start.needsInput ? `${phase.title} starts with you.` : `${phase.title} is the next step.`,
      text: i.start.needsInput ? "Write below what you want, then send." : "",
      primary: i.start.needsInput ? null : { id: "start", label: i.start.label, action: i.start.action },
      secondary: [],
    };
  }
  return null;
}
