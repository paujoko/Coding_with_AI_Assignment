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
