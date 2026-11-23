import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { Artifact, PhaseInfo, PhaseState } from "../api/types";
import { makeChange } from "../lib/changes.fixture";
import { PhaseWorkspace } from "./PhaseWorkspace";

// Maintenance as the developer meets it: the phase workspace with the tracker wired in.

const IDS = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];
const TITLES = ["Requirements", "Design", "Design refinement", "Code generation", "Testing", "Deployment", "Maintenance"];

const phases = (maintenance: PhaseState["status"]): PhaseState[] =>
  IDS.map((id, i) => ({ id, title: TITLES[i], status: id === "maintenance" ? maintenance : "approved", requires: [], implemented: true, can_run: true, updated_at: "", stale_cause: null }));

const info: PhaseInfo = {
  id: "maintenance",
  title: "Maintenance",
  summary: "",
  requires: ["deployment"],
  implemented: true,
  agents: [{ name: "impact_analyst", role: "", tier: "mid" }],
  actions: [
    { name: "change", label: "Request a change", description: "", input_schema: { properties: { request: { type: "string", description: "Describe the change" } }, required: ["request"] }, message_field: "request" },
    { name: "check", label: "Check consistency", description: "", input_schema: { properties: {} }, message_field: null },
    { name: "discuss", label: "Discuss", description: "", input_schema: { properties: { question: { type: "string", description: "Ask a question" } }, required: ["question"] }, message_field: "question" },
  ],
};

const changeArtifact: Artifact = {
  id: "change-1",
  kind: "change_request",
  phase: "maintenance",
  title: "Change 1",
  revision: 1,
  content: { number: 1, kind: "change", summary: "Tasks get a priority.", request: "Tasks need a priority", affected: [], steps: [] },
  text: "",
  path: null,
  defines: [],
  covers: [],
  author: "agent:impact_analyst",
  retired: false,
  created_at: "",
};

function workspace(over: Partial<React.ComponentProps<typeof PhaseWorkspace>> = {}) {
  const runs: [string, Record<string, unknown>][] = [];
  const all = over.all ?? phases("ready");
  const view = render(
    <PhaseWorkspace
      projectId="p"
      index={6}
      info={info}
      state={all[6]}
      all={all}
      messages={[]}
      events={[]}
      artifacts={[]}
      trace={null}
      canRender={false}
      busy={false}
      focus={{}}
      documents={[]}
      onUpload={async () => {
        throw new Error("not used");
      }}
      onRun={async (action, input) => {
        runs.push([action, input]);
        return true;
      }}
      onApprove={() => {}}
      onReopen={() => {}}
      onNext={() => {}}
      onStep={() => {}}
      onSaveContent={async () => {}}
      onSaveText={async () => {}}
      onOpenRequirement={() => {}}
      onOpenArtifact={() => {}}
      onOpenTrace={() => {}}
      onSetupDiagrams={() => {}}
      {...over}
    />,
  );
  return { ...view, runs };
}

test("an empty Maintenance shows three ways in; a change picks its action and puts the cursor in the input", () => {
  const { runs } = workspace();
  const ways = screen.getByRole("group", { name: "What to do in Maintenance" });
  expect(within(ways).getAllByRole("button")).toHaveLength(3);
  expect(screen.getByText("Ready", { selector: ".badge" })).toBeInTheDocument(); // not "Start"

  fireEvent.click(screen.getByRole("button", { name: "Discuss" })); // another action was chosen meanwhile
  fireEvent.click(within(ways).getByRole("button", { name: "Report a bug" }));
  expect(within(screen.getByRole("group", { name: "What to do" })).getByRole("button", { name: "Request a change" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByPlaceholderText("Describe the change")).toHaveFocus();
  expect(runs).toEqual([]);
});

test("check consistency runs at once", async () => {
  const { runs } = workspace();
  await act(async () => {
    fireEvent.click(within(screen.getByRole("group", { name: "What to do in Maintenance" })).getByRole("button", { name: "Check consistency" }));
  });
  expect(runs).toEqual([["check", {}]]);
});

test("an open change puts the tracker first in the results and the dock points at it instead of asking for approval", () => {
  const advanced: [number, boolean][] = [];
  const change = makeChange(1);
  workspace({
    all: phases("draft"),
    artifacts: [changeArtifact],
    changes: [change],
    openChange: { number: 1, done: 1, total: 6, next_phase: "design" },
    onAdvance: (c, through) => advanced.push([c.number, through]),
  });
  const results = screen.getByRole("region", { name: "Results" });
  expect(results.firstElementChild).toHaveAttribute("id", "change-tracker");
  expect(screen.getAllByText("Step 2 of 6", { selector: ".badge" }).length).toBeGreaterThan(0);
  expect(screen.getByText("Change #1 is at step 2 of 6.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(screen.getByRole("button", { name: /Tasks get a priority/ })).toHaveAttribute("aria-expanded", "false"); // the list row, collapsed

  fireEvent.click(screen.getByRole("button", { name: "Update the design" }));
  fireEvent.click(screen.getByRole("button", { name: "Carry it through" }));
  expect(advanced).toEqual([
    [1, false],
    [1, true],
  ]);
});

test("the latest completed change leads the results with its receipt", () => {
  workspace({ all: phases("draft"), artifacts: [changeArtifact], changes: [makeChange(6)], openChange: null });
  const results = screen.getByRole("region", { name: "Results" });
  expect(results.firstElementChild).toHaveAttribute("data-state", "complete");
  expect(within(results.firstElementChild as HTMLElement).getByRole("heading", { name: "What this change updated" })).toBeInTheDocument();
  expect(screen.getByText("Ready", { selector: ".badge" })).toBeInTheDocument(); // not "Review"
});

test("without tracked changes (older backend) Maintenance looks as before", () => {
  workspace({ all: phases("draft"), artifacts: [changeArtifact] });
  expect(document.getElementById("change-tracker")).toBeNull();
  expect(screen.getByText("Tasks need a priority")).toBeInTheDocument(); // the row is open
});
