import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { Artifact, PhaseInfo, PhaseState, PhaseStatus } from "../api/types";
import { DESIGN_GENERATE } from "../lib/choices.fixture";
import { PhaseWorkspace } from "./PhaseWorkspace";

const IDS = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];

function phases(statuses: Partial<Record<string, PhaseStatus>>, cause: string | null = null): PhaseState[] {
  const out: PhaseState[] = [];
  IDS.forEach((id, i) => {
    const can_run = i === 0 || out[i - 1].status === "approved";
    out.push({ id, title: id, status: statuses[id] ?? "locked", requires: i === 0 ? [] : [IDS[i - 1]], implemented: true, can_run, updated_at: "", stale_cause: statuses[id] === "stale" ? cause : null });
  });
  return out;
}

const action = (name: string, required: string[] = []) => ({
  name,
  label: name,
  description: "",
  message_field: required[0] ?? null,
  input_schema: { type: "object", properties: Object.fromEntries(required.map((r) => [r, { type: "string", description: r }])), required },
});

const CATALOG = [
  { id: "requirements", title: "Requirements", summary: "", requires: [], implemented: true, agents: [], actions: [action("start", ["description"]), action("revise", ["feedback"]), action("discuss", ["question"])] },
  { id: "design", title: "Design", summary: "", requires: [], implemented: true, agents: [], actions: [action("generate"), action("revise", ["feedback"]), action("discuss", ["question"])] },
  { id: "refinement", title: "Design refinement", summary: "", requires: [], implemented: true, agents: [], actions: [action("review"), action("discuss", ["question"])] },
  {
    id: "testing",
    title: "Testing",
    summary: "",
    requires: [],
    implemented: true,
    agents: [],
    actions: [
      {
        ...action("generate"),
        message_field: "guidance",
        input_schema: {
          type: "object",
          properties: {
            guidance: { type: "string", description: "Guidance (optional)" },
            depth: { type: "string", enum: ["focused", "thorough"], default: "focused", description: "How many tests" },
          },
          required: [],
        },
      },
      action("run"),
      action("discuss", ["question"]),
    ],
  },
] as unknown as PhaseInfo[];

const diagram: Artifact = {
  id: "classes",
  kind: "note",
  phase: "design",
  title: "Classes",
  revision: 1,
  content: {},
  text: "@startuml\n@enduml",
  path: null,
  defines: [],
  covers: [],
  author: "agent:architect",
  retired: false,
  created_at: "",
};

type Run = (action: string, input: Record<string, unknown>, attachments: string[]) => Promise<boolean>;

function show(all: PhaseState[], phase: string, redo: string[] = [], handlers: Partial<Record<"onAccept" | "onRedo" | "onKeep", () => void>> = {}, onRun: Run = async () => true) {
  const noop = () => {};
  return render(
    <PhaseWorkspace
      projectId="todo"
      info={CATALOG.find((c) => c.id === phase)!}
      catalog={CATALOG}
      state={all.find((p) => p.id === phase)!}
      all={all}
      redo={redo}
      messages={[]}
      events={[]}
      artifacts={[{ ...diagram, phase }]}
      trace={null}
      canRender={false}
      busy={false}
      focus={{}}
      documents={[]}
      onUpload={async () => ({ id: "a", name: "a", size: 0, chars: 0, created_at: "" }) as never}
      onRun={onRun}
      onAccept={handlers.onAccept ?? noop}
      onRedo={handlers.onRedo ?? noop}
      onKeep={handlers.onKeep ?? noop}
      onGo={noop}
      onStep={noop}
      onSaveContent={async () => {}}
      onSaveText={async () => {}}
      onOpenRequirement={noop}
      onOpenArtifact={noop}
      onOpenTrace={noop}
      onSetupDiagrams={noop}
    />,
  );
}

const solid = () => document.querySelectorAll(".action-bar .button-primary");

test("a result has one solid button, and it says what comes next", () => {
  const accepted: string[] = [];
  show(phases({ requirements: "approved", design: "draft" }), "design", [], { onAccept: () => accepted.push("design") });
  expect(solid()).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Accept and review the design" }));
  expect(accepted).toEqual(["design"]);
  expect(screen.getByText("Check that the diagrams cover every requirement.")).toHaveClass("marked-text");
});

test("a step that has to follow a change offers Redo, never Accept, and keeping it asks once", () => {
  const kept: string[] = [];
  show(phases({ requirements: "approved", design: "stale" }, "requirements"), "design", ["design"], { onKeep: () => kept.push("design") });
  expect(screen.getByRole("button", { name: "Redo Design" })).toHaveClass("button-primary");
  expect(screen.queryByRole("button", { name: /^Accept/ })).toBeNull();
  expect(screen.getByText(/Requirements changed after this was made/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Keep it unchanged" }));
  expect(kept).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Yes, keep it" }));
  expect(kept).toEqual(["design"]);
});

test("the text box means change this step; asking a question is the other choice, and it is reachable", async () => {
  const runs: [string, Record<string, unknown>][] = [];
  show(phases({ requirements: "approved", design: "draft" }), "design", [], {}, async (a, input) => (runs.push([a, input]), true));
  const modes = within(screen.getByRole("group", { name: "What to do" }));
  expect(modes.getByRole("button", { name: "Change it" })).toHaveAttribute("aria-pressed", "true");
  expect(modes.getByRole("button", { name: "Ask a question" })).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByPlaceholderText("Say what to change in this step")).toBeInTheDocument();
  fireEvent.click(modes.getByRole("button", { name: "Ask a question" }));
  fireEvent.change(screen.getByPlaceholderText("Ask the agent a question"), { target: { value: "Why a Task class?" } });
  fireEvent.submit(screen.getByRole("form", { name: "Message to the agent" }));
  await waitFor(() => expect(runs).toEqual([["discuss", { question: "Why a Task class?" }]]));
});

test("Tests: the text box asks by default, and Change the tests writes them again with the typed guidance", async () => {
  const runs: [string, Record<string, unknown>][] = [];
  const all = phases({ requirements: "approved", design: "approved", refinement: "approved", codegen: "approved", testing: "draft" });
  show(all, "testing", [], {}, async (a, input) => (runs.push([a, input]), true));
  const modes = within(screen.getByRole("group", { name: "What to do" }));
  // The change comes first, as on every step; the question stays the default here (session s04).
  expect(modes.getAllByRole("button").map((b) => b.textContent)).toEqual(["Change the tests", "Ask a question"]);
  expect(modes.getByRole("button", { name: "Ask a question" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(modes.getByRole("button", { name: "Change the tests" }));
  fireEvent.change(screen.getByPlaceholderText("Say what the tests should do differently"), { target: { value: "Fewer tests for the menu" } });
  fireEvent.submit(screen.getByRole("form", { name: "Message to the agent" }));
  await waitFor(() => expect(runs).toEqual([["generate", { guidance: "Fewer tests for the menu" }]]));
});

test("Design review changes through its findings: its box only asks, without a switch", () => {
  show(phases({ requirements: "approved", design: "approved", refinement: "draft" }), "refinement");
  expect(screen.queryByRole("group", { name: "What to do" })).toBeNull();
  expect(screen.getByPlaceholderText("Ask the agent a question")).toBeInTheDocument();
});

test("Design asks which diagrams first; the solid button draws exactly what is ticked (slim demo)", async () => {
  const runs: [string, Record<string, unknown>][] = [];
  const asking = CATALOG.map((c) => (c.id === "design" ? { ...c, actions: [DESIGN_GENERATE, ...c.actions.slice(1)] } : c));
  const all = phases({ requirements: "approved", design: "ready" });
  render(
    <PhaseWorkspace
      projectId="todo"
      info={asking.find((c) => c.id === "design")!}
      catalog={asking}
      state={all.find((p) => p.id === "design")!}
      all={all}
      redo={[]}
      messages={[]}
      events={[]}
      artifacts={[]}
      trace={null}
      canRender={false}
      busy={false}
      focus={{}}
      documents={[]}
      onUpload={async () => ({}) as never}
      onRun={async (a, input) => {
        runs.push([a, input]);
        return true;
      }}
      onAccept={() => {}}
      onRedo={() => {}}
      onKeep={() => {}}
      onGo={() => {}}
      onStep={() => {}}
      onSaveContent={async () => {}}
      onSaveText={async () => {}}
      onOpenRequirement={() => {}}
      onOpenArtifact={() => {}}
      onOpenTrace={() => {}}
      onSetupDiagrams={() => {}}
    />,
  );
  expect(screen.getByText("Choose the diagrams, then draw them.")).toHaveClass("marked-text");
  fireEvent.click(screen.getByRole("checkbox", { name: /^Sequence/ }));
  fireEvent.click(screen.getByRole("radio", { name: /^Detailed/ }));
  fireEvent.click(screen.getByRole("button", { name: "Draw the design" }));
  expect(runs).toEqual([["generate", { kinds: ["use_case", "class"], level: "detailed" }]]);

  for (const kind of ["Use case", "Class"]) fireEvent.click(screen.getByRole("checkbox", { name: new RegExp(`^${kind}`) }));
  expect(screen.queryByRole("button", { name: "Draw the design" })).toBeNull();
  expect(screen.getByText("Tick at least one diagram.")).toBeInTheDocument();
});
