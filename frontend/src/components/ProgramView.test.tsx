import { fireEvent, render, screen } from "@testing-library/react";
import type { PhaseInfo, PhaseState } from "../api/types";
import type { Outgoing } from "../lib/outbox";
import { ProgramView } from "./ProgramView";

const IDS = ["requirements", "design", "refinement", "codegen", "testing", "deployment", "maintenance"];
const all: PhaseState[] = IDS.map((id, i) => ({ id, title: id, status: "approved", requires: i ? [IDS[i - 1]] : [], implemented: true, can_run: true, updated_at: "", stale_cause: null }));
const text = (name: string, field: string) => ({ name, label: name, description: "", message_field: field, input_schema: { properties: { [field]: { type: "string" as const, description: field } }, required: [field] } });
const info = { id: "maintenance", title: "Maintenance", summary: "", requires: [], implemented: true, agents: [], actions: [text("change", "request"), text("discuss", "question")] } as unknown as PhaseInfo;

const change = (state: Outgoing["state"]): Outgoing => ({
  id: 3,
  project: "p",
  phase: "maintenance",
  action: "change",
  input: { request: "Tasks get tags" },
  attachments: [],
  message: { phase: "maintenance", role: "developer", text: "Tasks get tags", author: "developer", data: {}, created_at: "2026-11-25T10:00:00Z" },
  state,
  seen: 0,
});

type Props = Parameters<typeof ProgramView>[0];
function mount(extra: Partial<Props>) {
  const noop = () => {};
  const props: Props = {
    info,
    state: all[6],
    all,
    redo: [],
    messages: [],
    events: [],
    artifacts: [],
    runGuide: null,
    deployCheck: null,
    trace: null,
    designCheck: null,
    changes: [],
    busy: false,
    folder: null,
    onRun: async () => true,
    onProbe: noop,
    onGo: noop,
    onStep: noop,
    onOpenFolder: noop,
    onOpenRequirement: noop,
    onOpenArtifact: noop,
    ...extra,
  };
  const r = render(<ProgramView {...props} />);
  return { again: (more: Partial<Props>) => r.rerender(<ProgramView {...props} {...more} />) };
}

test("a change sent from Your program shows at once in the conversation, with the working line", () => {
  mount({ busy: true, running: "maintenance", busySince: new Date().toISOString(), pending: [change("sending")] });
  expect(screen.getByRole("button", { name: /^Conversation/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByText("Tasks get tags").closest("li")).toHaveAttribute("data-state", "sending");
  expect(screen.getByText("Working out what the change touches")).toBeInTheDocument();
});

test("a change that was not sent stays, with Try again", async () => {
  const retried: string[] = [];
  const { again } = mount({ busy: true, running: "maintenance", pending: [change("sending")], onRetry: async (o) => (retried.push(o.action), true) });
  again({ busy: false, running: null, pending: [change("failed")] });
  expect(screen.getByText("Not sent")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retried).toEqual(["change"]);
});

test("while another step works, Your program can be read but its change box waits and says why", () => {
  mount({ busy: true, running: "codegen" });
  expect(screen.getByText("Changes wait until Code is done.")).toBeInTheDocument();
  expect(document.querySelector(".send")).toBeDisabled();
  expect(screen.queryByText("Working out what the change touches")).toBeNull();
});
