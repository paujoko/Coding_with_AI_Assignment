import type { PhaseState, Trace } from "../api/types";
import { Icon } from "./Icon";

interface Props {
  trace: Trace | null;
  phases: PhaseState[];
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase: string) => void;
}

// Requirement x artifact matrix. Computed by the backend from the trace IDs, never by an LLM.
export function TraceView({ trace, phases, onOpenRequirement, onOpenArtifact }: Props) {
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

  return (
    <section className="page" aria-labelledby="trace-heading">
      <header className="page-head">
        <h1 id="trace-heading">Traceability</h1>
        <p className="lede">
          {covered} of {total} requirements appear in at least one artifact. Checked by code from the trace IDs, not by a model.
        </p>
      </header>
      {trace.unknown_refs.length > 0 && (
        <p className="notice" role="status">
          <Icon name="alert" size={14} /> Artifacts refer to requirements that do not exist: {trace.unknown_refs.join(", ")}.
        </p>
      )}
      {trace.artifacts.length === 0 ? (
        <p className="empty-note">No diagrams yet. Approve the requirements and generate the design to fill this matrix.</p>
      ) : (
        <div className="matrix-wrap">
          <table className="matrix">
            <thead>
              <tr>
                <th scope="col" className="matrix-corner">
                  Requirement
                </th>
                {trace.artifacts.map((a) => (
                  <th key={a.id} scope="col" className="matrix-col">
                    <button type="button" className="link" onClick={() => onOpenArtifact(a.id, a.phase)}>
                      {a.title}
                    </button>
                    <span className="matrix-phase">{phaseTitle(a.phase)}</span>
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
                      <button type="button" className="matrix-req" onClick={() => onOpenRequirement(r.id)}>
                        <span className="req-id">{r.id}</span>
                        <span>{r.title}</span>
                      </button>
                    </th>
                    {trace.artifacts.map((a) => (
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
