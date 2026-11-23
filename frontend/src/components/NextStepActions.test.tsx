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
  expect(screen.getByText("The program is ready to run.")).toBeInTheDocument();
  const run = screen.getByRole("button", { name: "Run it" });
  expect(run).toHaveClass("button-primary");
  expect(screen.getByRole("button", { name: /Go to Maintenance/ })).not.toHaveClass("button-primary");
  fireEvent.click(run);
  expect(asked).toBe(1);

  const results = screen.getByRole("region", { name: "Results" });
  expect(within(results).getAllByRole("heading", { level: 2 })[0]).toHaveTextContent("Run it");
  expect(within(results).getByText('cd "C:\\dev\\todo"')).toBeInTheDocument();
});

test("a finished project offers Run it from other approved steps; an unfinished one does not", () => {
  const all = phases();
  const props = { ...base, index: 0, info: info("requirements", ["start"]), artifacts: [], onRunIt: () => {}, onRun: async () => true };
  const { rerender } = render(<PhaseWorkspace {...props} state={all[0]} all={all} />);
  expect(screen.getByRole("button", { name: "Run it" })).not.toHaveClass("button-primary");
  expect(screen.getByRole("button", { name: /Go to Design/ })).toHaveClass("button-primary");

  const open = phases({ deployment: "draft" });
  rerender(<PhaseWorkspace {...props} state={open[0]} all={open} />);
  expect(screen.queryByRole("button", { name: "Run it" })).not.toBeInTheDocument();
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
