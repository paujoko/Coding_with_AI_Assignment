import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Change } from "../api/types";
import { makeChange } from "../lib/changes.fixture";
import { ChangeTracker } from "./ChangeTracker";

function show(change: Change, over: Partial<React.ComponentProps<typeof ChangeTracker>> = {}) {
  const calls = { phases: [] as string[], artifacts: [] as [string, string][], requirements: [] as string[] };
  const view = render(
    <ChangeTracker
      change={change}
      running={false}
      activePhase={null}
      busy={false}
      onOpenPhase={(p) => calls.phases.push(p)}
      onOpenRequirement={(r) => calls.requirements.push(r)}
      onOpenArtifact={(a, p) => calls.artifacts.push([a, p])}
      {...over}
    />,
  );
  return { ...view, calls };
}

test("an open change at rest is the request, what it affects and one compact progress line: no step list, no buttons", () => {
  const { calls } = show(makeChange(2));
  expect(screen.getByRole("heading", { name: "Change #1" })).toBeInTheDocument();
  expect(screen.getByText("Tasks need a priority")).toBeInTheDocument();
  expect(screen.getByText("Change", { selector: ".tag" })).toBeInTheDocument();
  expect(screen.getByText("2 of 6 steps updated")).toBeInTheDocument();
  expect(screen.queryByText(/Step 3 of 6/)).toBeNull(); // the status is said once, in the card above the input
  expect(screen.queryByRole("list", { name: "Steps of this change" })).toBeNull();
  expect(screen.queryByRole("button", { name: /Carry it through|Update the/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "REQ-002" }));
  expect(calls.requirements).toEqual(["REQ-002"]);
});

test("while an update runs the full list of steps shows, the running one marked", () => {
  const { container, calls } = show(makeChange(2), { running: true, activePhase: "refinement", busy: true });
  const steps = within(screen.getByRole("list", { name: "Steps of this change" })).getAllByRole("listitem");
  expect(steps.map((li) => li.getAttribute("data-state"))).toEqual(["done", "done", "current", "waiting", "waiting", "waiting"]);
  expect(within(steps[0]).getByText("Done")).toBeInTheDocument();
  expect(within(steps[0]).getByText("1 updated")).toBeInTheDocument(); // from the receipt
  expect(within(steps[2]).getByText("Running")).toBeInTheDocument();
  expect(within(steps[5]).getByText("Waiting")).toBeInTheDocument();
  expect(container.querySelectorAll('[data-state="done"] .track-icon svg')).toHaveLength(2);
  expect(calls.phases).toEqual([]);
  expect(screen.queryByText("2 of 6 steps updated")).toBeNull();
});

test("phases a bug does not move read as not affected in the running list", () => {
  const bug = makeChange(3, { kind: "bug" });
  bug.progress.phases = bug.progress.phases.map((p, i) => (i < 3 ? { ...p, state: "untouched", updated: false } : p));
  bug.progress.total = 3;
  bug.progress.done = 0;
  show(bug, { running: true, activePhase: "codegen" });
  expect(screen.getAllByText("Not affected")).toHaveLength(3);
  expect(screen.getByText("Bug")).toBeInTheDocument();
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

test("a completed change is its receipt: no steps, the totals as the headline", () => {
  show(makeChange(6));
  expect(screen.getByText(/^Carried through/)).toBeInTheDocument();
  expect(screen.getByText("6 updated in 6 steps")).toBeInTheDocument();
  expect(screen.queryByRole("list", { name: "Steps of this change" })).toBeNull();
  expect(screen.queryByText(/steps updated/)).toBeNull();
  expect(screen.getAllByRole("button", { name: /artifact$/ })).toHaveLength(6);
});

test("links are off while an agent works", () => {
  show(makeChange(2), { busy: true });
  expect(screen.getByRole("button", { name: "REQ-001" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Design artifact" })).toBeDisabled();
});
