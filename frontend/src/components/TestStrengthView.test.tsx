import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Artifact, Trace } from "../api/types";
import { TestReportView } from "./TestReportView";
import { TestStrengthView, trimCommonIndent } from "./TestStrengthView";

const mutant = (over: Record<string, unknown>) => ({
  id: "M1",
  path: "todo/cli.py",
  line: 17,
  column: 11,
  operator: "negation",
  description: "removed `not`",
  original: "        if not args:",
  mutated: "        if args:",
  outcome: "caught",
  tests: ["test_req_003_missing_number_names_it"],
  requirements: ["REQ-003"],
  reason: "",
  seconds: 1.1,
  ...over,
});

const strength = (mutants: Record<string, unknown>[], over: Record<string, unknown> = {}): Artifact => ({
  id: "test-strength",
  kind: "test_strength",
  phase: "testing",
  title: "Injected bugs",
  revision: 1,
  content: {
    caught: mutants.filter((m) => m.outcome === "caught").length,
    survived: mutants.filter((m) => m.outcome === "survived").length,
    invalid: mutants.filter((m) => m.outcome === "invalid").length,
    total: mutants.length,
    score: 0.5,
    by_requirement: { "REQ-003": 1 },
    seconds: 9.23,
    report_revision: 1,
    mutants,
    ...over,
  },
  text: "",
  path: "reports/test-strength.md",
  defines: [],
  covers: [],
  author: "system:mutation",
  retired: false,
  created_at: "2026-11-23T10:00:00Z",
});

const trace = (s: Trace["strength"]): Trace => ({ covered: {}, uncovered: [], unknown_refs: [], ratio: 1, requirements: [], artifacts: [], results: {}, strength: s });

const three = [
  mutant({ id: "M1" }),
  mutant({ id: "M2", line: 19, description: "`==` became `!=`", original: "    return a == b", mutated: "    return a != b", outcome: "survived", tests: [], requirements: [] }),
  mutant({ id: "M3", line: 30, outcome: "invalid", tests: [], requirements: [], reason: "The run hit the time limit (probably an endless loop)." }),
];

test("one verdict line, survivors first, then caught with the failed test and its requirement, invalid last", () => {
  const opened: string[] = [];
  render(
    <TestStrengthView
      strength={strength(three)}
      trace={trace({ caught: 1, survived: 1, invalid: 1, total: 3, score: 0.5, by_requirement: {} })}
      reportRevision={1}
      busy={false}
      onOpenRequirement={(id) => opened.push(id)}
    />,
  );
  expect(screen.getByText("1 of 2 injected bugs caught.")).toBeInTheDocument();
  expect(screen.getByText("Checked by code")).toBeInTheDocument();
  expect(screen.queryByText(/Out of date/)).not.toBeInTheDocument();

  const rows = screen.getAllByRole("listitem");
  expect(rows.map((r) => r.getAttribute("data-outcome"))).toEqual(["survived", "caught", "invalid"]);
  expect(within(rows[0]).getByText("No test noticed this")).toBeInTheDocument();
  expect(screen.getByText(/every test still passed/)).toBeInTheDocument();
  expect(within(rows[1]).getByText("test_req_003_missing_number_names_it")).toBeInTheDocument();
  fireEvent.click(within(rows[1]).getByRole("button", { name: "REQ-003" }));
  expect(opened).toEqual(["REQ-003"]);
  expect(within(rows[2]).getByText(/Did not count: The run hit the time limit/)).toBeInTheDocument();

  // The change as two lines without the shared indentation.
  const diff = within(rows[1]).getByLabelText("The change in todo/cli.py, line 17");
  expect(diff.querySelector('[data-kind="original"]')?.textContent).toContain("if not args:");
  expect(diff.querySelector('[data-kind="original"]')?.textContent).not.toContain("  if not");
  expect(diff.querySelector('[data-kind="mutated"]')?.textContent).toContain("if args:");
});

test("a check older than the code or the latest run is marked as out of date", () => {
  const { rerender } = render(<TestStrengthView strength={strength(three)} trace={trace(null)} reportRevision={1} busy={false} onOpenRequirement={() => {}} />);
  expect(screen.getByText(/Out of date/)).toBeInTheDocument();
  // An older backend sends no strength field: then only the run number decides.
  rerender(<TestStrengthView strength={strength(three)} trace={trace(undefined)} reportRevision={1} busy={false} onOpenRequirement={() => {}} />);
  expect(screen.queryByText(/Out of date/)).not.toBeInTheDocument();
  rerender(<TestStrengthView strength={strength(three)} trace={trace(undefined)} reportRevision={2} busy={false} onOpenRequirement={() => {}} />);
  expect(screen.getByText(/Out of date/)).toBeInTheDocument();
});

test("common indentation is cut, the difference in indentation is kept", () => {
  expect(trimCommonIndent("        if not args:", "        if args:")).toEqual(["if not args:", "if args:"]);
  expect(trimCommonIndent("    return x", "      return None  ")).toEqual(["return x", "  return None"]);
});

test("the test results offer Inject bugs only for a green run", () => {
  const report = (green: boolean): Artifact => ({
    ...strength([]),
    id: "test-report",
    kind: "test_report",
    content: { tests: [], passed: green ? 3 : 2, failed: green ? 0 : 1, errors: 0, green, verified: {}, seconds: 1, output: "" },
  });
  let ran = 0;
  const { rerender } = render(<TestReportView report={report(true)} busy={false} onOpenRequirement={() => {}} onProbe={() => ran++} />);
  fireEvent.click(screen.getByRole("button", { name: "Inject bugs" }));
  expect(ran).toBe(1);
  rerender(<TestReportView report={report(true)} busy onOpenRequirement={() => {}} onProbe={() => ran++} />);
  expect(screen.getByRole("button", { name: "Inject bugs" })).toBeDisabled();
  rerender(<TestReportView report={report(false)} busy={false} onOpenRequirement={() => {}} onProbe={() => ran++} />);
  expect(screen.queryByRole("button", { name: "Inject bugs" })).not.toBeInTheDocument();
});
