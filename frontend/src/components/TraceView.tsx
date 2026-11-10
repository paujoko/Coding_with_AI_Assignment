import type { PhaseState, Trace } from "../api/types";
import { VERDICT_LABEL } from "../api/types";
import { Icon } from "./Icon";

interface Props {
  trace: Trace | null;
  phases: PhaseState[];
  busy: boolean;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase: string) => void;
}

const TRACED = new Set(["diagram", "source_file", "test_file"]);

// Requirement x artifact matrix. Computed by the backend from the trace IDs, never by an LLM.
export function TraceView({ trace, phases, busy, onOpenRequirement, onOpenArtifact }: Props) {
  if (!trace || trace.requirements.length === 0) {
    return (
      <section className="page">
        <header className="page-head">
          <h1>Traceability</h1>
          <p className="lede">Which requirement appears in which diagram, and later in which file and test.</p>
        </header>
        <p className="empty-note">Nothing to trace yet. Requirements get their IDs in P1; diagrams link to them in P2.</p>
      </section>
    );
  }
  const phaseTitle = (id: string) => phases.find((p) => p.id === id)?.title ?? id;
  const total = trace.requirements.length;
  const covered = total - trace.uncovered.length;
  // Columns: what implements a requirement (diagrams, code, tests), grouped by the phase that made it.
  const order = phases.map((p) => p.id);
  const columns = trace.artifacts
    .filter((a) => TRACED.has(a.kind) && (a.kind === "diagram" || a.covers.length > 0)) // a file that traces to nothing adds an empty column
    .sort((a, b) => order.indexOf(a.phase) - order.indexOf(b.phase));
  const groups = columns.reduce<{ phase: string; span: number }[]>((acc, a) => {
    const last = acc.at(-1);
    if (last?.phase === a.phase) last.span += 1;
    else acc.push({ phase: a.phase, span: 1 });
    return acc;
  }, []);
  const results = trace.results ?? {};
  const ran = Object.keys(results).length > 0;
  const verified = trace.requirements.filter((r) => results[r.id] === "passed").length;

  return (
    <section className="page" aria-labelledby="trace-heading">
      <header className="page-head">
        <h1 id="trace-heading">Traceability</h1>
        <p className="lede">
          {covered} of {total} requirements appear in at least one artifact
          {ran ? `, ${verified} are verified by passing tests` : ""}. Checked by code from the trace IDs, not by a model.
        </p>
      </header>
      {trace.unknown_refs.length > 0 && (
        <p className="notice" role="status">
          <Icon name="alert" size={14} /> Artifacts refer to requirements that do not exist: {trace.unknown_refs.join(", ")}.
        </p>
      )}
      {columns.length === 0 ? (
        <p className="empty-note">Nothing traces to the requirements yet. Approve them and generate the design to fill this matrix.</p>
      ) : (
        <div className="matrix-wrap">
          <table className="matrix">
            <thead>
              <tr className="matrix-groups">
                <td />
                {ran && <td />}
                {groups.map((g) => (
                  <th key={g.phase} scope="colgroup" colSpan={g.span}>
                    {phaseTitle(g.phase)}
                  </th>
                ))}
              </tr>
              <tr>
                <th scope="col" className="matrix-corner">
                  Requirement
                </th>
                {ran && (
                  <th scope="col" className="matrix-col matrix-result">
                    Latest test
                  </th>
                )}
                {columns.map((a) => (
                  <th key={a.id} scope="col" className="matrix-col">
                    <button type="button" className="link" disabled={busy} title={a.title} onClick={() => onOpenArtifact(a.id, a.phase)}>
                      {a.kind === "diagram" ? a.title : a.title.split("/").pop()}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trace.requirements.map((r) => {
                const by = new Set(trace.covered[r.id] ?? []);
                return (
                  <tr key={r.id} data-uncovered={by.size === 0 || undefined}>
                    <th scope="row">
                      <button type="button" className="matrix-req" disabled={busy} onClick={() => onOpenRequirement(r.id)}>
                        <span className="req-id">{r.id}</span>
                        <span>{r.title}</span>
                      </button>
                    </th>
                    {ran && (
                      <td className="matrix-result">
                        <span className="outcome" data-outcome={results[r.id] ?? "none"}>
                          {results[r.id] ? (VERDICT_LABEL[results[r.id]] ?? results[r.id]) : "no test"}
                        </span>
                      </td>
                    )}
                    {columns.map((a) => (
                      <td key={a.id}>
                        {by.has(a.id) ? (
                          <span className="hit" role="img" aria-label={`${r.id} in ${a.title}`} />
                        ) : (
                          <span className="sr-only">not in {a.title}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
