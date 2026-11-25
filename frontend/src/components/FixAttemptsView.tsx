import type { FixAttempt } from "../api/types";

const names = (list: string[]) => (list.length ? list.join(", ") : "none");

/** What the run after an attempt showed; the same words as the backend (domain/fixloop.py). */
export function attemptOutcome(a: FixAttempt): string {
  if (a.after === null) return "The tests were not run again yet after it.";
  const after = a.after;
  if (after.length === 0) return "After it: all tests pass.";
  const fixed = a.failing.filter((n) => !after.includes(n));
  const still = a.failing.filter((n) => after.includes(n));
  const fresh = after.filter((n) => !a.failing.includes(n));
  const parts = [`still failing: ${names(still)}`];
  if (fixed.length) parts.unshift(`fixed: ${names(fixed)}`);
  if (fresh.length) parts.push(`newly failing: ${names(fresh)}`);
  return `After it, ${parts.join("; ")}.`;
}

const CAUSE = { code: "the code", test: "the test", environment: "the environment" };

// P5: the attempts of the current fix loop. The debugger reads the same list, so it does not repeat a fix that did not help.
export function FixAttemptsView({ attempts }: { attempts: FixAttempt[] }) {
  if (attempts.length === 0) return null;
  return (
    <section className="fix-attempts" aria-labelledby="fix-attempts-heading">
      <h2 id="fix-attempts-heading">Fix attempts</h2>
      <ol>
        {attempts.map((a) => (
          <li key={a.number}>
            <strong>
              Attempt {a.number}: {CAUSE[a.cause] ?? a.cause}.
            </strong>{" "}
            {a.diagnosis}
            {a.changed.length > 0 && <span className="fix-changed"> Changed {a.changed.join(", ")}.</span>}
            <span className="fix-outcome">{attemptOutcome(a)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
