import type { Artifact, TestRun } from "../api/types";
import { Icon } from "./Icon";

interface Props {
  report: Artifact;
  busy: boolean;
  onOpenRequirement: (id: string) => void;
}

const OUTCOME_LABEL = { passed: "Passed", failed: "Failed", error: "Error", skipped: "Skipped" };

// P5: the result of running pytest for real. Nothing here comes from a model.
export function TestReportView({ report, busy, onOpenRequirement }: Props) {
  const c = report.content;
  const tests: TestRun[] = c.tests ?? [];
  const failing = tests.filter((t) => t.outcome === "failed" || t.outcome === "error");
  const ordered = [...failing, ...tests.filter((t) => !failing.includes(t))];

  return (
    <section className="doc" aria-labelledby="results-heading">
      <header className="doc-head">
        <div>
          <h2 id="results-heading">Test results</h2>
          <p className="meta">
            pytest ran {tests.length} {tests.length === 1 ? "test" : "tests"} in {Number(c.seconds ?? 0).toFixed(1)} s{" "}
            <span aria-hidden="true">·</span> run {report.revision}
          </p>
        </div>
      </header>
      <div className="verdict" data-ok={c.green || undefined} role="status">
        <Icon name={c.green ? "check" : "alert"} />
        <p>
          <strong>{c.green ? "All tests pass." : "Some tests do not pass."}</strong> {c.passed} passed, {c.failed} failed, {c.errors} errors.
          {Object.keys(c.verified ?? {}).length > 0 && ` Verified by passing tests: ${Object.entries(c.verified).filter(([, o]) => o === "passed").length} requirements.`}
        </p>
      </div>
      {tests.length > 0 && (
        <ul className="checks" aria-label="Tests">
          {ordered.map((t) => (
            <li key={`${t.classname}.${t.name}`} data-outcome={t.outcome}>
              <span className="check-mark" aria-hidden="true">
                <Icon name={t.outcome === "passed" ? "check" : t.outcome === "skipped" ? "chevron" : "close"} size={12} />
              </span>
              <span className="sr-only">{OUTCOME_LABEL[t.outcome]}: </span>
              <span className="check-name">{t.name}</span>
              {t.requirement && (
                <button type="button" className="req-chip" disabled={busy} onClick={() => onOpenRequirement(t.requirement!)}>
                  {t.requirement}
                </button>
              )}
              {t.message && t.outcome !== "passed" && <span className="check-detail">{t.message.split("\n")[0]}</span>}
            </li>
          ))}
        </ul>
      )}
      {c.output && (
        <details className="console">
          <summary>Console output</summary>
          <pre className="raw">{c.output}</pre>
        </details>
      )}
    </section>
  );
}
