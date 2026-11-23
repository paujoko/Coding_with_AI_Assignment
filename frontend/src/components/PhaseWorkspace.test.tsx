import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Artifact, PhaseInfo, PhaseState, PhaseStatus } from "../api/types";
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

function show(all: PhaseState[], phase: string, redo: string[] = [], handlers: Partial<Record<"onAccept" | "onRedo" | "onKeep", () => void>> = {}) {
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
      onRun={async () => true}
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

test("the text box means change this step; asking a question is the other choice", () => {
  show(phases({ requirements: "approved", design: "draft" }), "design");
  const modes = within(screen.getByRole("group", { name: "What to do" }));
  expect(modes.getByRole("button", { name: "Change it" })).toHaveAttribute("aria-pressed", "true");
  expect(modes.getByRole("button", { name: "Ask a question" })).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByPlaceholderText("Say what to change in this step")).toBeInTheDocument();
});
