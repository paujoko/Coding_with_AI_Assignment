import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Change } from "../api/types";
import type { CarryRun } from "../lib/changes";
import { makeChange } from "../lib/changes.fixture";
import { ChangeDockNote, ChangeTracker } from "./ChangeTracker";

function show(change: Change, over: Partial<React.ComponentProps<typeof ChangeTracker>> = {}) {
  const calls = { advance: [] as [number, boolean][], phases: [] as string[], artifacts: [] as [string, string][], requirements: [] as string[], stops: 0 };
  const view = render(
    <ChangeTracker
      change={change}
      run={null}
      busy={false}
      onAdvance={(c, through) => calls.advance.push([c.number, through])}
      onStop={() => (calls.stops += 1)}
      onOpenPhase={(p) => calls.phases.push(p)}
      onOpenRequirement={(r) => calls.requirements.push(r)}
      onOpenArtifact={(a, p) => calls.artifacts.push([a, p])}
      {...over}
    />,
  );
  return { ...view, calls };
}

const run = (over: Partial<CarryRun>): CarryRun => ({
  change: 1,
  through: true,
  active: false,
  current: null,
  steps: [],
  stopping: false,
  stopped: null,
  stoppedPhase: null,
  failed: null,
  complete: false,
  ...over,
});

test("an open change shows the request, its kind, the affected requirements and the six steps with their states", () => {
  const { container, calls } = show(makeChange(2));
  expect(screen.getByRole("heading", { name: "Change #1" })).toBeInTheDocument();
  expect(screen.getByText("Tasks need a priority")).toBeInTheDocument();
  expect(screen.getByText("Change", { selector: ".tag" })).toBeInTheDocument();
  expect(screen.getByText("Step 3 of 6")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "REQ-002" }));
  expect(calls.requirements).toEqual(["REQ-002"]);

  const steps = within(screen.getByRole("list", { name: "Steps of this change" })).getAllByRole("listitem");
  expect(steps.map((li) => li.getAttribute("data-state"))).toEqual(["done", "done", "current", "waiting", "waiting", "waiting"]);
  expect(within(steps[0]).getByText("Done")).toBeInTheDocument();
  expect(within(steps[0]).getByText("1 updated")).toBeInTheDocument(); // from the receipt
  expect(within(steps[2]).getByText("Now")).toBeInTheDocument();
  expect(within(steps[2]).getByRole("button")).toHaveAttribute("aria-current", "step");
  expect(within(steps[5]).getByText("Waiting")).toBeInTheDocument();
  expect(container.querySelectorAll('[data-state="done"] .track-icon svg')).toHaveLength(2); // ticks, as in the sidebar
  fireEvent.click(within(steps[3]).getByRole("button"));
  expect(calls.phases).toEqual(["codegen"]);
});

test("phases a bug does not move read as not affected", () => {
  const bug = makeChange(3, { kind: "bug" });
  bug.progress.phases = bug.progress.phases.map((p, i) => (i < 3 ? { ...p, state: "untouched", updated: false } : p));
  bug.progress.total = 3;
  bug.progress.done = 0;
  show(bug);
  expect(screen.getAllByText("Not affected")).toHaveLength(3);
  expect(screen.getByText("Bug")).toBeInTheDocument();
  expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
});

test("the primary button is named for the next step and runs one step; carry it through is the other choice", () => {
  const { calls } = show(makeChange(1));
  const primary = screen.getByRole("button", { name: "Update the design" });
  expect(primary).toHaveClass("button-primary");
  fireEvent.click(primary);
  fireEvent.click(screen.getByRole("button", { name: "Carry it through" }));
  expect(calls.advance).toEqual([
    [1, false],
    [1, true],
  ]);
  expect(screen.getByText(/approves each one whose code checks pass/)).toBeInTheDocument(); // said honestly
});

test("a phase that waits for approval offers to approve it or to look first", () => {
  const change = makeChange(4);
  change.next = { ...change.next!, kind: "approve", steps: [] };
  const { calls } = show(change);
  fireEvent.click(screen.getByRole("button", { name: "Approve the tests" }));
  fireEvent.click(screen.getByRole("button", { name: "Look at the tests" }));
  expect(calls.advance).toEqual([[1, false]]);
  expect(calls.phases).toEqual(["testing"]);
});

test("open questions and failed checks say why and lead to the phase, with nothing to run", () => {
  const change = makeChange(4);
  change.next = { ...change.next!, kind: "blocked", steps: [], reason: "Some tests do not pass. Fix the code or the tests." };
  const { calls } = show(change);
  expect(screen.getByText("Some tests do not pass. Fix the code or the tests.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Carry it through" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Open Testing" }));
  expect(calls.phases).toEqual(["testing"]);
  expect(calls.advance).toEqual([]);
});

test("while it is carried through: what ran, what Wings approved, the running phase and a way to stop after it", () => {
  const live = run({
    active: true,
    steps: [{ phase: "design", title: "Design", ran: ["Revise"], approved: true, seconds: 42 }],
    current: { phase: "refinement", title: "Design refinement", doing: "Updating the refined design", since: new Date().toISOString() },
  });
  const { calls, rerender } = show(makeChange(2), { run: live, busy: true });
  expect(screen.getByText("Updated the design. Wings approved it: its code checks pass.")).toBeInTheDocument();
  expect(screen.getByText("0:42")).toBeInTheDocument();
  expect(screen.getByText("Updating the refined design")).toBeInTheDocument();
  expect(screen.getByText("Running")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Carry it through" })).toBeNull(); // no second start while it runs
  fireEvent.click(screen.getByRole("button", { name: "Stop after this step" }));
  expect(calls.stops).toBe(1);

  rerender(
    <ChangeTracker change={makeChange(2)} run={{ ...live, stopping: true }} busy onAdvance={() => {}} onStop={() => {}} onOpenPhase={() => {}} onOpenRequirement={() => {}} onOpenArtifact={() => {}} />,
  );
  expect(screen.getByRole("button", { name: "Stops after this step" })).toBeDisabled();
});

test("after a stop the reason stands above the buttons, and the step can be tried again", () => {
  const stopped = run({
    stopped: "Code generation: the step did not finish. The model did not answer.",
    stoppedPhase: "codegen",
    steps: [{ phase: "refinement", title: "Design refinement", ran: ["Refresh"], approved: true, seconds: 3 }],
  });
  show(makeChange(3), { run: stopped });
  expect(screen.getByText("Code generation: the step did not finish. The model did not answer.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Code generation" })).toHaveClass("link"); // the way to look at it
  expect(screen.getByRole("button", { name: "Update the code" })).toBeEnabled();
});

test("a stop the next step already explains is not said twice", () => {
  const reason = "Some tests do not pass. Fix the code or the tests.";
  const change = makeChange(4);
  change.next = { ...change.next!, kind: "blocked", steps: [], reason };
  show(change, { run: run({ stopped: reason, stoppedPhase: "testing" }) });
  expect(screen.getAllByText(new RegExp(reason.slice(0, 20)))).toHaveLength(1);
});

test("a refused request is told in the tracker", () => {
  show(makeChange(3), { run: run({ failed: "Another action is still running on this project.", stoppedPhase: "codegen" }) });
  expect(screen.getByRole("alert")).toHaveTextContent("That step did not run. Another action is still running on this project.");
});

test("the run of another change is not shown", () => {
  show(makeChange(3), { run: run({ change: 7, failed: "nope" }) });
  expect(screen.queryByRole("alert")).toBeNull();
});

test("the receipt lists per phase what was updated, added and removed, and links every artifact to its phase", () => {
  const change = makeChange(2);
  change.receipt[1] = {
    phase: "design",
    title: "Design",
    updated: [
      { id: "class-diagram", title: "Domain classes", kind: "diagram", path: "design/classes.puml", before: 2, after: 3, changed: true },
      { id: "use-cases", title: "Use cases", kind: "diagram", path: "design/use-cases.puml", before: 1, after: 2, changed: false },
    ],
    added: [{ id: "seq-priority", title: "Set a priority", kind: "diagram", path: null, before: null, after: 1, changed: true }],
    removed: [{ id: "old", title: "Old sequence", kind: "diagram", path: null, before: 1, after: 1, changed: true }],
  };
  const { calls } = show(change);
  const receipt = screen.getByRole("region", { name: "What this change updated" });
  expect(within(receipt).getByText("Checked by code")).toBeInTheDocument();
  expect(within(receipt).getByText("2 updated, 1 added, 1 removed in 2 steps")).toBeInTheDocument();

  const row = (name: string) => within(receipt).getByText(name).closest("li")!;
  expect(row("Domain classes")).toHaveTextContent("revision 2 to 3");
  expect(row("Use cases")).toHaveTextContent("rewritten, identical");
  expect(row("Use cases")).toHaveAttribute("data-what", "identical");
  expect(row("Set a priority")).toHaveTextContent("new");
  expect(row("Old sequence")).toHaveTextContent("removed");
  expect(within(row("Old sequence")).queryByRole("button")).toBeNull(); // nothing left to open

  fireEvent.click(within(receipt).getByRole("button", { name: "Domain classes" }));
  expect(calls.artifacts).toEqual([["class-diagram", "design"]]);
  expect(within(receipt).getByText("Nothing so far in Design refinement, Code generation, Testing, Deployment.")).toBeInTheDocument();
});

test("a change that has not started says that nothing was updated yet", () => {
  show(makeChange(0));
  expect(screen.getByText("Nothing updated yet.")).toBeInTheDocument();
});

test("a completed change is its receipt: no steps to run, the totals as the headline", () => {
  show(makeChange(6));
  expect(screen.getByText(/^Carried through/)).toBeInTheDocument();
  expect(screen.getByText("6 updated in 6 steps")).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "Steps of this change" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Carry it through" })).toBeNull();
  expect(screen.getAllByRole("button", { name: /artifact$/ })).toHaveLength(6);
});

test("links are off while an agent works", () => {
  show(makeChange(2), { busy: true });
  expect(screen.getByRole("button", { name: "Update the refined design" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "REQ-001" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Design artifact" })).toBeDisabled();
});

test("the dock of Maintenance points at the tracker", () => {
  let shown = 0;
  render(<ChangeDockNote open={{ number: 2, done: 2, total: 6, next_phase: "codegen" }} nextTitle="Code generation" onShow={() => (shown += 1)} />);
  expect(screen.getByText("Change #2 is at step 3 of 6.")).toBeInTheDocument();
  expect(screen.getByText(/Next: Code generation\./)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show the change" }));
  expect(shown).toBe(1);
});
