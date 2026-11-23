import { act, fireEvent, render, renderHook, screen, within } from "@testing-library/react";
import type { Artifact, Message, PhaseState } from "../api/types";
import { advanced, makeChange } from "../lib/changes.fixture";
import { useCarry } from "../lib/useCarry";
import { Conversation } from "./Conversation";
import { ChangesView, MaintenanceStart } from "./MaintenanceViews";
import { where } from "./ProjectSwitcher";
import { StepList } from "./StepList";

const ids = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];
const titles = ["Requirements", "Design", "Design refinement", "Code generation", "Testing", "Deployment", "Maintenance"];

function phases(maintenance: PhaseState["status"]): PhaseState[] {
  return ids.map((id, i) => ({
    id,
    title: titles[i],
    status: id === "maintenance" ? maintenance : "approved",
    requires: i === 0 ? [] : [ids[i - 1]],
    implemented: true,
    can_run: true,
    updated_at: "",
    stale_cause: null,
  }));
}

const artifact = (number: number, summary: string): Artifact => ({
  id: `change-${number}`,
  kind: "change_request",
  phase: "maintenance",
  title: `Change ${number}`,
  revision: 1,
  content: { number, kind: "change", summary, request: `Request ${number}`, affected: ["REQ-001"], impact: { "REQ-001": [{ id: "classes", title: "Domain classes", kind: "diagram" }] }, steps: ["Update the requirements"] },
  text: "",
  path: null,
  defines: [],
  covers: [],
  author: "agent:impact_analyst",
  retired: false,
  created_at: "",
});

// ---------- Sidebar and switcher ----------

test("while a change is open the Maintenance step says nothing: the steps it moves say Update", () => {
  const all = phases("draft");
  all[3] = { ...all[3], status: "stale" };
  render(<StepList phases={all} selected={null} onSelect={() => {}} />);
  const step = screen.getByRole("button", { name: /Maintenance/ });
  expect(within(step).getByText("Ready")).toHaveClass("sr-only");
  expect(screen.getByText("Update")).toHaveClass("step-word");
  expect(screen.queryByText(/Step 2 of 6/)).toBeNull();
});

test("with no open change the Maintenance step reads as ready, with no word to act on", () => {
  for (const status of ["ready", "draft"] as const) {
    const { unmount } = render(<StepList phases={phases(status)} selected={null} onSelect={() => {}} />);
    const step = screen.getByRole("button", { name: /Maintenance/ });
    expect(step).toHaveAttribute("data-status", "ready");
    expect(within(step).getByText("Ready")).toHaveClass("sr-only");
    expect(screen.queryByText("Start")).toBeNull();
    expect(screen.queryByText("Review")).toBeNull();
    unmount();
  }
});

test("other steps keep their words, and an out-of-date Maintenance asks for a check", () => {
  const all = phases("stale");
  all[1] = { ...all[1], status: "draft" };
  render(<StepList phases={all} selected={null} onSelect={() => {}} />);
  expect(screen.getByText("Review")).toHaveClass("step-word");
  expect(within(screen.getByRole("button", { name: /Maintenance/ })).getByText("Check")).toHaveClass("step-word");
});

test("the project switcher line says the same", () => {
  expect(where({ phases: phases("draft"), open_change: { number: 2, done: 3, total: 6, next_phase: "testing" } })).toBe("Change #2 in progress");
  expect(where({ phases: phases("ready"), open_change: null })).toBe("Maintenance: ready");
  expect(where({ phases: phases("draft") })).toBe("Maintenance: ready");
  const design = phases("locked");
  design[1] = { ...design[1], status: "draft" };
  expect(where({ phases: design, open_change: null })).toBe("Design: review");
});

// ---------- Empty state ----------

test("an empty Maintenance offers three ways in", () => {
  const picked: string[] = [];
  render(<MaintenanceStart onChange={() => picked.push("change")} onBug={() => picked.push("bug")} onCheck={() => picked.push("check")} />);
  const ways = within(screen.getByRole("group", { name: "What to do in Maintenance" })).getAllByRole("button");
  expect(ways.map((b) => b.textContent)).toEqual(["Change something", "Report a bug", "Check consistency"]);
  ways.forEach((b) => fireEvent.click(b));
  expect(picked).toEqual(["change", "bug", "check"]);
});

// ---------- The list of changes ----------

test("tracked changes are collapsed rows with their state; opening an older one shows its receipt", () => {
  const done = makeChange(6, { number: 1 });
  const open = makeChange(2, { number: 2 });
  render(
    <ChangesView
      changes={[artifact(1, "Tasks get a priority."), artifact(2, "Tasks get a due date.")]}
      tracked={[open, done]}
      featured={2}
      busy={false}
      onOpenRequirement={() => {}}
      onOpenArtifact={() => {}}
    />,
  );
  const rows = screen.getAllByRole("button", { expanded: false });
  expect(rows).toHaveLength(2);
  expect(rows[0]).toHaveTextContent("#2"); // newest first
  expect(rows[0]).toHaveTextContent("In progress, step 3 of 6");
  expect(rows[1]).toHaveTextContent("Carried through: 6 updated");
  expect(screen.queryByText("Request 1")).toBeNull();

  fireEvent.click(rows[1]);
  expect(screen.getByText("Request 1")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "What this change updated" })).toBeInTheDocument();

  // The newest change is in the tracker above: its row adds impact and plan, not the receipt again.
  fireEvent.click(rows[0]);
  expect(screen.getByText("Request 2")).toBeInTheDocument();
  expect(screen.getAllByRole("region", { name: "What this change updated" })).toHaveLength(1);
});

test("without tracking (older backend) the newest change is open as before", () => {
  render(<ChangesView changes={[artifact(1, "First"), artifact(2, "Second")]} busy={false} onOpenRequirement={() => {}} onOpenArtifact={() => {}} />);
  expect(screen.getByText("Request 2")).toBeInTheDocument();
  expect(screen.queryByText("Request 1")).toBeNull();
  expect(screen.queryByText(/In progress/)).toBeNull();
});

// ---------- The chat ----------

const reply: Message = {
  phase: "maintenance",
  role: "agent",
  text: "Change: Tasks get a priority.\nTouches REQ-001; 4 artifact(s) trace to REQ-001.\nPhases that move: Requirements, Design.\nCarry the change through with the button below: Wings updates one phase after the other.",
  author: "agent:impact_analyst",
  data: { change: 1, next_actions: [{ label: "Update the requirements", phase: "requirements", action: "revise", input: { feedback: "Add a priority." } }] },
  created_at: "2026-11-23T10:26:30Z",
};

function chat(trackedChanges: number[] | undefined, onStep = (_: unknown) => {}) {
  return render(
    <Conversation intro="" messages={[reply]} events={[]} agentName="Impact analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} canStep onStep={onStep} trackedChanges={trackedChanges} />,
  );
}

test("the answer that created a tracked change is short and has no button of its own: the card above the input has the one next step", () => {
  chat([1]);
  expect(screen.getByText(/Tasks get a priority/)).toBeInTheDocument();
  expect(screen.queryByText(/Phases that move/)).toBeNull();
  expect(screen.queryByText(/button below/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Update the requirements" })).toBeNull();
});

test("without tracking the answer is shown as the agent wrote it, its proposal is a quiet button", () => {
  const steps: unknown[] = [];
  chat(undefined, (s) => steps.push(s));
  expect(screen.getByText(/Phases that move/)).toBeInTheDocument();
  const button = screen.getByRole("button", { name: "Update the requirements" });
  expect(button).not.toHaveClass("button-primary");
  fireEvent.click(button);
  expect(steps).toHaveLength(1);
});

test("an empty conversation can show its own start", () => {
  render(<Conversation intro="One line" messages={[]} events={[]} agentName="Impact analyst" busy={false} answers={{}} canAnswer={false} onPick={() => {}} empty={<p>Three ways in</p>} />);
  expect(screen.getByText("Three ways in")).toBeInTheDocument();
  expect(screen.queryByText("One line")).toBeNull();
});

// ---------- The hook behind the tracker's buttons ----------

function carryHook(advance: (pid: string, n: number, approve: boolean) => ReturnType<typeof advanced> | Promise<ReturnType<typeof advanced>>) {
  const log: string[] = [];
  const guarded = async (work: () => Promise<void>) => {
    log.push("busy");
    await work();
    log.push("idle");
    return true;
  };
  const hook = renderHook(() =>
    useCarry({
      projectId: "todo",
      guarded,
      advance: async (pid, n, approve) => advance(pid, n, approve),
      onAdvanced: async (r) => {
        log.push(`refresh ${r.change.progress.done}`);
      },
      onFailed: async (pid) => {
        log.push(`reload ${pid}`);
      },
    }),
  );
  return { ...hook, log };
}

test("carrying a change through is one busy stretch with a refresh after every phase", async () => {
  let done = 4;
  const { result, log } = carryHook(() => {
    done += 1;
    return advanced(makeChange(done), { approved: "x" });
  });
  await act(async () => {
    await result.current.start(makeChange(4), true);
  });
  expect(log).toEqual(["busy", "refresh 5", "refresh 6", "idle"]);
  expect(result.current.run).toMatchObject({ active: false, complete: true, change: 1 });
  expect(result.current.run?.steps).toHaveLength(2);
});

test("a refused request (409) ends the run, is kept for the tracker and reloads the project", async () => {
  const { result, log } = carryHook(() => {
    throw new Error("An agent is already working on this project.");
  });
  await act(async () => {
    await result.current.start(makeChange(2), true);
  });
  expect(log).toEqual(["busy", "reload todo", "idle"]);
  expect(result.current.run).toMatchObject({ active: false, failed: "An agent is already working on this project." });
});

test("stop after this step marks the run and ends it after the running phase", async () => {
  let release: (() => void) | undefined;
  const { result } = carryHook(async () => {
    await new Promise<void>((r) => (release = r));
    return advanced(makeChange(3), { approved: "refinement" });
  });
  let finished: Promise<boolean> | undefined;
  await act(async () => {
    finished = result.current.start(makeChange(2), true);
    await Promise.resolve();
  });
  expect(result.current.run).toMatchObject({ active: true, stopping: false, current: { phase: "refinement" } });
  act(() => result.current.requestStop());
  expect(result.current.run?.stopping).toBe(true);
  await act(async () => {
    release?.();
    await finished;
  });
  expect(result.current.run).toMatchObject({ active: false, stopped: "You stopped it after Design refinement.", stoppedPhase: null });
  expect(result.current.run?.steps).toHaveLength(1);
});
