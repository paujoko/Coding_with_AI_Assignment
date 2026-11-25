import type { Artifact, Mutant, Trace } from "../api/types";
import { CheckedByCode } from "./CheckedByCode";
import { Covers } from "./Covers";
import { Icon } from "./Icon";

interface Props {
  strength: Artifact;
  trace: Trace | null;
  reportRevision?: number | null; // the latest test run; a check made for an older run is out of date
  busy: boolean;
  onOpenRequirement: (id: string) => void;
  onProbe?: () => void; // inject bugs again; absent when the step cannot run it now
}

/** The two lines of a change without the indentation they share, so the difference starts at the left edge. */
export function trimCommonIndent(original: string, mutated: string): [string, string] {
  const lines = [original, mutated].map((l) => l.replace(/\s+$/, "").replace(/\t/g, "    "));
  const indent = Math.min(...lines.filter((l) => l.trim()).map((l) => l.length - l.trimStart().length), Infinity);
  const cut = Number.isFinite(indent) ? indent : 0;
  return [lines[0].slice(cut), lines[1].slice(cut)];
}

const OUTCOME_LABEL: Record<Mutant["outcome"], string> = {
  caught: "Caught",
  survived: "No test noticed this",
  invalid: "Did not count",
};

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function Row({ m, onOpenRequirement }: { m: Mutant; onOpenRequirement: (id: string) => void }) {
  const [original, mutated] = trimCommonIndent(m.original ?? "", m.mutated ?? "");
  return (
    <li className="mutant" data-outcome={m.outcome}>
      <p className="mutant-head">
        <span className="check-mark" aria-hidden="true">
          <Icon name={m.outcome === "caught" ? "check" : m.outcome === "survived" ? "alert" : "chevron"} size={12} />
        </span>
        <span className="mutant-where">
          {m.path} <span className="mutant-line">line {m.line}</span>
        </span>
        <span className="mutant-what">{m.description}</span>
        <span className="mutant-outcome">{OUTCOME_LABEL[m.outcome] ?? m.outcome}</span>
      </p>
      <pre className="mutant-diff" aria-label={`The change in ${m.path}, line ${m.line}`}>
        <span className="diff-line" data-kind="original">
          <span className="diff-tag">code</span>
          {original || " "}
          {"\n"}
        </span>
        <span className="diff-line" data-kind="mutated">
          <span className="diff-tag">bug</span>
          {mutated || " "}
        </span>
      </pre>
      {m.outcome === "caught" && (m.tests ?? []).length > 0 && (
        <div className="mutant-proof">
          <p className="mutant-tests">
            <span className="trace-label">Failed, as it should</span>
            {m.tests.map((t) => (
              <code key={t}>{t}</code>
            ))}
          </p>
          <Covers ids={m.requirements ?? []} label="Tests of" onOpen={onOpenRequirement} />
        </div>
      )}
      {m.outcome === "survived" && m.reason && <p className="mutant-reason">{m.reason}</p>}
      {m.outcome === "invalid" && <p className="mutant-reason">Did not count: {m.reason || "the run gave no usable result."}</p>}
    </li>
  );
}

// P5: Wings put small bugs into the code, one at a time, and ran the tests against each. The rows are the
// evidence: which change, which test failed because of it, and which changes no test noticed.
export function TestStrengthView({ strength, trace, reportRevision, busy, onOpenRequirement, onProbe }: Props) {
  const c = strength.content;
  const mutants: Mutant[] = c.mutants ?? [];
  const caught = Number(c.caught ?? mutants.filter((m) => m.outcome === "caught").length);
  const survived = Number(c.survived ?? mutants.filter((m) => m.outcome === "survived").length);
  const invalid = Number(c.invalid ?? mutants.filter((m) => m.outcome === "invalid").length);
  const judged = caught + survived;
  const groups: [Mutant["outcome"], string][] = [
    ["survived", "No test noticed these"],
    ["caught", "Caught by a test"],
    ["invalid", "Did not count"],
  ];
  // Bugs caught in old code say nothing about the new code: the backend drops the counts from the trace then.
  const outdated = trace?.strength === null || (reportRevision != null && c.report_revision != null && c.report_revision !== reportRevision);
  const tone = judged === 0 ? "none" : survived === 0 ? "ok" : "warn";

  return (
    <section className="doc strength" aria-labelledby="strength-heading">
      <header className="doc-head">
        <div>
          <h2 id="strength-heading">Injected bugs</h2>
          <p className="meta">
            Wings changed one line at a time and ran the tests against each change
            {c.seconds != null && `, ${Number(c.seconds).toFixed(1)} s`} <span aria-hidden="true">·</span> run {strength.revision}{" "}
            <span aria-hidden="true">·</span> <CheckedByCode />
          </p>
        </div>
        {onProbe && (
          <button type="button" className="button" disabled={busy} onClick={onProbe}>
            <Icon name="refresh" size={14} />
            Inject bugs again
          </button>
        )}
      </header>
      {outdated && (
        <p className="notice strength-old" role="status">
          <Icon name="alert" size={14} />
          <span>Out of date: the code or the tests changed after these bugs were injected.</span>
        </p>
      )}
      <div className="verdict" data-ok={tone === "ok" || undefined} data-tone={tone} role="status">
        <Icon name={tone === "ok" ? "check" : "alert"} />
        <p>
          <strong>{judged === 0 ? "No injected bug could be judged." : `${caught} of ${judged} injected bugs caught.`}</strong>
          {survived > 0 && ` ${survived === 1 ? "1 went" : `${survived} went`} unnoticed by every test.`}
          {invalid > 0 && ` ${invalid} more did not count.`}
        </p>
      </div>
      {groups.map(([outcome, title]) => {
        const rows = mutants.filter((m) => m.outcome === outcome);
        if (rows.length === 0) return null;
        return (
          <div key={outcome} className="mutant-group" data-outcome={outcome}>
            <h3>
              {title} <span className="mutant-count">{rows.length}</span>
            </h3>
            {outcome === "survived" && (
              <p className="mutant-why">
                With {rows.length === 1 ? "this bug" : "each of these bugs"} in the code, every test still passed, so a real mistake on{" "}
                {rows.length === 1 ? "this line" : "these lines"} would go unnoticed. A change that does not alter what the program does cannot be caught by any test.
              </p>
            )}
            <ul className="mutants" aria-label={`${title}: ${plural(rows.length, "injected bug")}`}>
              {rows.map((m) => (
                <Row key={m.id} m={m} onOpenRequirement={onOpenRequirement} />
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}
