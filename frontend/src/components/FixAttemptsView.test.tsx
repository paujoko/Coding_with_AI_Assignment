import { render, screen } from "@testing-library/react";
import { FixAttemptsView, attemptOutcome } from "./FixAttemptsView";
import type { FixAttempt } from "../api/types";

const attempt = (over: Partial<FixAttempt>): FixAttempt => ({
  number: 1,
  failing: ["test_a", "test_b"],
  cause: "code",
  diagnosis: "complete() never sets done.",
  fix: "Set task.done = True.",
  changed: [],
  after: null,
  ...over,
});

test("each attempt says what the next run showed, as the backend computes it", () => {
  expect(attemptOutcome(attempt({}))).toBe("The tests were not run again yet after it.");
  expect(attemptOutcome(attempt({ after: [] }))).toBe("After it: all tests pass.");
  expect(attemptOutcome(attempt({ after: ["test_b", "test_c"] }))).toBe("After it, fixed: test_a; still failing: test_b; newly failing: test_c.");
});

test("the fix loop lists its attempts, newest last, with the files a test fix changed", () => {
  render(
    <FixAttemptsView
      attempts={[attempt({ after: ["test_b"] }), attempt({ number: 2, cause: "test", failing: ["test_b"], changed: ["tests/test_tasks.py"] })]}
    />,
  );
  expect(screen.getByRole("heading", { name: "Fix attempts" })).toBeInTheDocument();
  expect(screen.getByText(/Attempt 2/)).toBeInTheDocument();
  expect(screen.getByText(/Changed tests\/test_tasks\.py/)).toBeInTheDocument();
  expect(screen.getByText("After it, fixed: test_a; still failing: test_b.")).toBeInTheDocument();
});
