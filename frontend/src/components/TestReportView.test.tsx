import { render, screen } from "@testing-library/react";
import type { Artifact } from "../api/types";
import { TestReportView } from "./TestReportView";

test("requirements with a declared gap are named as not verified although their tests pass", () => {
  // Real run (s03): REQ-015 "runs in the browser" showed as verified for a terminal program.
  const report: Artifact = {
    id: "test-report",
    kind: "test_report",
    phase: "testing",
    title: "Test results",
    revision: 1,
    content: {
      tests: [{ name: "test_req_001_add", classname: "t", outcome: "passed", message: "", requirement: "REQ-001" }],
      passed: 1,
      failed: 0,
      errors: 0,
      green: true,
      verified: { "REQ-001": "passed", "REQ-013": "partial", "REQ-015": "not_met" },
      seconds: 1,
      output: "",
    },
    text: "",
    path: null,
    defines: [],
    covers: [],
    author: "system:pytest",
    retired: false,
    created_at: "2026-11-09T10:00:00Z",
  };
  render(<TestReportView report={report} busy={false} onOpenRequirement={() => {}} />);
  expect(screen.getByText(/Verified by passing tests: 1 requirements\./)).toBeInTheDocument();
  expect(screen.getByText(/REQ-013 \(partly tested\), REQ-015 \(not met\)/)).toBeInTheDocument();
});

test("a failing test shows the file, line and code where it failed", () => {
  // Real run 2026-11-25: failures were only "..F..F"; the line is what the developer and the debugger need.
  const report: Artifact = {
    id: "test-report",
    kind: "test_report",
    phase: "testing",
    title: "Test results",
    revision: 2,
    content: {
      tests: [
        {
          name: "test_req_003_complete_a_task",
          classname: "tests.test_tasks",
          outcome: "failed",
          message: "assert False",
          requirement: "REQ-003",
          path: "tests/test_tasks.py",
          where: [{ path: "tests/test_tasks.py", line: 43, code: "assert service.list()[0].done" }],
        },
      ],
      passed: 0,
      failed: 1,
      errors: 0,
      green: false,
      verified: { "REQ-003": "failed" },
      seconds: 1,
      output: "",
    },
    text: "",
    path: null,
    defines: [],
    covers: [],
    author: "system:pytest",
    retired: false,
    created_at: "2026-11-25T10:00:00Z",
  };
  render(<TestReportView report={report} busy={false} onOpenRequirement={() => {}} />);
  expect(screen.getByText("tests/test_tasks.py:43")).toBeInTheDocument();
  expect(screen.getByText("assert service.list()[0].done")).toBeInTheDocument();
});

function jsReport(content: Record<string, unknown>): Artifact {
  return {
    id: "test-report",
    kind: "test_report",
    phase: "testing",
    title: "Test results",
    revision: 3,
    content: { passed: 1, failed: 0, errors: 0, green: true, verified: { "REQ-001": "passed" }, seconds: 1, output: "", ...content },
    text: "",
    path: null,
    defines: [],
    covers: [],
    author: "system:pytest",
    retired: false,
    created_at: "2026-11-25T10:00:00Z",
  };
}

test("the report says how many requirements are verified and marks JavaScript tests (ADR 0020)", () => {
  // Real run 2026-11-25 (Flappy Bird): 49 green pytest tests, the game logic in game.js untested, 1 of 19 verified.
  const report = jsReport({
    tests: [
      { name: "test_req_001_add", classname: "t", outcome: "passed", message: "", requirement: "REQ-001", runner: "pytest" },
      { name: "REQ-002 a task line", classname: "tests/tasks.test.js", outcome: "passed", message: "", requirement: "REQ-002", runner: "node" },
    ],
    passed: 2,
    node: { ran: true, files: 1, reason: null, seconds: 0.4 },
    verification: { total: 19, verified: ["REQ-001", "REQ-002"], partial: [], not_met: [], failing: [], skipped: [], no_result: [], summary: "2 of 19 requirements verified by a passing test; 17 without a test result." },
  });
  render(<TestReportView report={report} busy={false} onOpenRequirement={() => {}} />);
  expect(screen.getByText(/2 of 19 requirements verified by a passing test; 17 without a test result\./)).toBeInTheDocument();
  expect(screen.getByText(/pytest and node ran 2 tests/)).toBeInTheDocument();
  expect(screen.getAllByText("node")).toHaveLength(1);
});

test("JavaScript tests that could not run are said, never shown as passed", () => {
  const report = jsReport({
    tests: [{ name: "tests/tasks.test.js", classname: "tests/tasks.test.js", outcome: "skipped", message: "JS tests not run: node not found", requirement: null, runner: "node" }],
    node: { ran: false, files: 1, reason: "node not found", seconds: 0 },
  });
  render(<TestReportView report={report} busy={false} onOpenRequirement={() => {}} />);
  expect(screen.getByText("JS tests not run: node not found.")).toBeInTheDocument();
});
