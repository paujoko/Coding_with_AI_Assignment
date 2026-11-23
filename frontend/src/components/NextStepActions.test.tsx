import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Artifact, PhaseInfo, PhaseState } from "../api/types";
import { readyToRun } from "../lib/status";
import { PhaseWorkspace } from "./PhaseWorkspace";

const IDS = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];
const title = (id: string) => id.charAt(0).toUpperCase() + id.slice(1);

const phases = (status: Partial<Record<string, PhaseState["status"]>> = {}): PhaseState[] =>
  IDS.map((id) => ({
    id,
    title: title(id),
    status: status[id] ?? (id === "maintenance" ? "ready" : "approved"),
    requires: [],
    implemented: true,
    can_run: true,
    updated_at: "",
    stale_cause: null,
  }));

const info = (id: string, actions: string[]): PhaseInfo => ({
  id,
  title: title(id),
  summary: "",
  requires: [],
  implemented: true,
  agents: [],
  actions: actions.map((name) => ({
    name,
    label: name === "probe" ? "Inject bugs" : title(name),
    description: "",
    input_schema: (name === "probe" ? { properties: { limit: { type: "integer", default: 8 } } } : { properties: {} }) as PhaseInfo["actions"][number]["input_schema"],
    message_field: null,
  })),
});

const art = (over: Partial<Artifact>): Artifact => ({
  id: "x",
  kind: "x",
  phase: "testing",
  title: "x",
  revision: 1,
  content: {},
  text: "",
  path: null,
  defines: [],
  covers: [],
  author: "system:x",
  retired: false,
  created_at: "",
  ...over,
});

const base = {
  projectId: "p",
  messages: [],
  events: [],
  trace: null,
  canRender: false,
  busy: false,
  focus: {},
  documents: [],
  onUpload: async () => {
    throw new Error("not used");
  },
  onApprove: () => {},
  onReopen: () => {},
  onNext: () => {},
  onStep: () => {},
  onSaveContent: async () => {},
  onSaveText: async () => {},
  onOpenRequirement: () => {},
  onOpenArtifact: () => {},
  onOpenTrace: () => {},
  onSetupDiagrams: () => {},
};

const guide = art({ id: "run-guide", kind: "run_guide", phase: "deployment", content: { start_command: "python -m todo", url: null, example_commands: [], stop_hint: "", checked: true, derived: false } });

test("an approved Deployment offers Run it first, and the card with the commands is the first result", () => {
  let asked = 0;
  const all = phases();
  render(
    <PhaseWorkspace
      {...base}
      index={5}
      info={info("deployment", ["generate", "check"])}
      state={all[5]}
      all={all}
      artifacts={[art({ id: "deployment-check", kind: "deployment_check", phase: "deployment", content: { passed: true, problems: [] } }), guide]}
      folder={"C:\\dev\\todo"}
      onRunIt={() => asked++}
      onRun={async () => true}
    />,
  );
  expect(screen.getByText("Your project is ready.")).toBeInTheDocument();
  const run = screen.getByRole("button", { name: "Run it" });
  expect(run).toHaveClass("button-primary");
  expect(screen.getByRole("button", { name: "Change something" })).not.toHaveClass("button-primary");
  fireEvent.click(run);
  expect(asked).toBe(1);

  const results = screen.getByRole("region", { name: "Results" });
  expect(within(results).getAllByRole("heading", { level: 2 })[0]).toHaveTextContent("Run it");
  expect(within(results).getByText('cd "C:\\dev\\todo"')).toBeInTheDocument();
});

test("a finished project offers Run it as the one next step on other approved steps; an unfinished one goes on to the next step", () => {
  const all = phases();
  const props = { ...base, index: 0, info: info("requirements", ["start"]), artifacts: [], onRunIt: () => {}, onRun: async () => true };
  const { rerender } = render(<PhaseWorkspace {...props} state={all[0]} all={all} />);
  expect(screen.getByRole("button", { name: "Run it" })).toHaveClass("button-primary");
  expect(screen.queryByRole("button", { name: /Go to Design/ })).toBeNull(); // one next step, not two

  const open = phases({ deployment: "draft" });
  rerender(<PhaseWorkspace {...props} state={open[0]} all={open} />);
  expect(screen.queryByRole("button", { name: "Run it" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Go to Design/ })).toHaveClass("button-primary");
  expect(readyToRun(all)).toBe(true);
  expect(readyToRun(open)).toBe(false);
  expect(readyToRun(phases({ testing: "stale" }))).toBe(false);
});

test("Testing with a green run offers Inject bugs, which runs probe at once without input", async () => {
  const ran: [string, Record<string, unknown>][] = [];
  const all = phases({ testing: "draft", deployment: "locked" });
  const report = art({ id: "test-report", kind: "test_report", content: { tests: [], passed: 3, failed: 0, errors: 0, green: true, verified: {}, seconds: 1, output: "" } });
  const props = {
    ...base,
    index: 4,
    info: info("testing", ["generate", "run", "probe"]),
    state: all[4],
    all,
    onRun: async (action: string, input: Record<string, unknown>) => {
      ran.push([action, input]);
      return true;
    },
  };
  const { rerender } = render(<PhaseWorkspace {...props} artifacts={[report]} />);
  // In the next-step card (before approving) and in the head of the test results.
  const buttons = screen.getAllByRole("button", { name: "Inject bugs" }).filter((b) => !b.hasAttribute("aria-pressed"));
  expect(buttons).toHaveLength(2);
  fireEvent.click(buttons[0]);
  await screen.findByRole("region", { name: "Results" });
  expect(ran).toEqual([["probe", {}]]);

  // Once the bugs were injected for this run, the card is calm again; the view offers a new round.
  const strength = art({ id: "test-strength", kind: "test_strength", content: { caught: 1, survived: 0, invalid: 0, total: 1, score: 1, by_requirement: {}, report_revision: 1, mutants: [] } });
  rerender(<PhaseWorkspace {...props} artifacts={[report, strength]} />);
  expect(screen.getAllByRole("button", { name: "Inject bugs" }).filter((b) => !b.hasAttribute("aria-pressed"))).toHaveLength(0);
  expect(screen.getByRole("button", { name: "Inject bugs again" })).toBeInTheDocument();
  expect(screen.getByText("1 of 1 injected bugs caught.")).toBeInTheDocument();

  // A red run cannot be probed.
  rerender(<PhaseWorkspace {...props} artifacts={[art({ ...report, content: { ...report.content, green: false } })]} />);
  expect(screen.queryAllByRole("button", { name: "Inject bugs" }).filter((b) => !b.hasAttribute("aria-pressed"))).toHaveLength(0);
});

// ---------- Out of date means Update ----------

const staleBase = () => {
  const all = phases({ design: "stale", refinement: "stale", codegen: "stale", testing: "stale" });
  all[1] = { ...all[1], stale_cause: "requirements" };
  return all;
};

test("an out-of-date step has no Approve: Update all N steps, and Keep as it is asks once more", () => {
  const updates: boolean[] = [];
  let approved = 0;
  const all = staleBase();
  render(
    <PhaseWorkspace
      {...base}
      index={1}
      info={info("design", ["generate", "revise"])}
      state={all[1]}
      all={all}
      artifacts={[]}
      stale={["design", "refinement", "codegen", "testing"]}
      onUpdate={(only) => updates.push(only)}
      onApprove={() => approved++}
      onRun={async () => true}
    />,
  );
  expect(screen.queryByRole("button", { name: /^Approve/ })).toBeNull();
  expect(screen.getByText("Design is out of date.")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Requirements changed after this was made.");
  const primary = screen.getByRole("button", { name: "Update all 4 steps" });
  expect(primary).toHaveClass("button-primary");
  fireEvent.click(screen.getByRole("button", { name: "Update this step only" }));
  fireEvent.click(primary);
  expect(updates).toEqual([true, false]);

  // Keeping needs a second click and says what it means; nothing is approved before it.
  fireEvent.click(screen.getByRole("button", { name: "Keep as it is" }));
  expect(approved).toBe(0);
  expect(screen.getByText("Keep Design as it is?")).toBeInTheDocument();
  expect(screen.getByText("The later steps may no longer match it.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByText("Design is out of date.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Keep as it is" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, keep it" }));
  expect(approved).toBe(1);
});

test("while the update runs the card shows the progress and Stop, and nothing else to press", () => {
  let stopped = 0;
  const all = staleBase();
  render(
    <PhaseWorkspace
      {...base}
      busy
      index={1}
      info={info("design", ["generate", "revise"])}
      state={all[1]}
      all={all}
      artifacts={[]}
      stale={["design", "refinement", "codegen", "testing"]}
      update={{ active: true, only: false, total: 4, current: { phase: "codegen", title: "Code generation", index: 2, since: new Date().toISOString() }, steps: [], stopping: false, stopped: null, stoppedPhase: null, failed: null, complete: false }}
      onStopUpdate={() => stopped++}
      onRun={async () => true}
    />,
  );
  expect(screen.getByText("Updating Code generation...")).toBeInTheDocument();
  expect(screen.getByText("2 of 4")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Update all/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect(stopped).toBe(1);
});

test("a later step of a finished one is offered as the one thing to do", () => {
  const updates: boolean[] = [];
  const all = phases({ design: "stale", refinement: "stale" });
  render(
    <PhaseWorkspace
      {...base}
      index={0}
      info={info("requirements", ["start"])}
      state={all[0]}
      all={all}
      artifacts={[]}
      stale={["design", "refinement"]}
      onUpdate={(only) => updates.push(only)}
      onRun={async () => true}
    />,
  );
  expect(screen.getByText("2 steps are out of date.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Update all 2 steps" }));
  expect(updates).toEqual([false]);
  expect(screen.queryByRole("button", { name: /Go to Design/ })).toBeNull();
});
