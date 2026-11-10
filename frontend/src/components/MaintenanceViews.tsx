import type { Artifact, RequirementProgress } from "../api/types";
import { VERDICT_LABEL } from "../api/types";
import { Icon } from "./Icon";

const KIND_LABEL: Record<string, string> = { bug: "Bug", change: "Change", new_requirement: "New requirement" };
const PHASE_TITLE: Record<string, string> = {
  diagram: "Diagram",
  source_file: "Code",
  test_file: "Test",
  deployment_file: "Deployment",
};

interface Linking {
  busy: boolean;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string) => void;
}

// P7: every change request with what it touches (from the trace) and the plan, newest first.
export function ChangesView({ changes, busy, onOpenRequirement, onOpenArtifact }: { changes: Artifact[] } & Linking) {
  const sorted = [...changes].sort((a, b) => (b.content.number ?? 0) - (a.content.number ?? 0));
  return (
    <section className="doc" aria-labelledby="changes-heading">
      <header className="doc-head">
        <div>
          <h2 id="changes-heading">Changes</h2>
          <p className="meta">
            {changes.length} {changes.length === 1 ? "request" : "requests"}; what each touches is computed from the trace IDs
          </p>
        </div>
      </header>
      <ol className="changes">
        {sorted.map((ch) => {
          const c = ch.content;
          const impact: Record<string, { id: string; title: string; kind: string }[]> = c.impact ?? {};
          return (
            <li key={ch.id} className="change">
              <p className="change-head">
                <span className="req-id">#{c.number}</span>
                <span className="tag" data-kind={c.kind}>
                  {KIND_LABEL[c.kind] ?? c.kind}
                </span>
                <strong>{c.summary}</strong>
              </p>
              <blockquote className="change-request">{c.request}</blockquote>
              {(c.affected ?? []).length > 0 && (
                <dl className="impact">
                  {(c.affected as string[]).map((rid) => (
                    <div key={rid}>
                      <dt>
                        <button type="button" className="req-chip" disabled={busy} onClick={() => onOpenRequirement(rid)}>
                          {rid}
                        </button>
                      </dt>
                      <dd>
                        {(impact[rid] ?? []).length === 0
                          ? "Nothing traces to it yet."
                          : impact[rid].map((a) => (
                              <button key={a.id} type="button" className="link impact-item" disabled={busy} onClick={() => onOpenArtifact(a.id)}>
                                <span className="impact-kind">{PHASE_TITLE[a.kind] ?? a.kind}</span> {a.title}
                              </button>
                            ))}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
              {(c.steps ?? []).length > 0 && (
                <ol className="plan">
                  {(c.steps as string[]).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

const yes = (ok: boolean, label: string) => (
  <span className="mark" data-ok={ok || undefined} role="img" aria-label={`${label}: ${ok ? "yes" : "no"}`}>
    {ok ? <Icon name="check" size={12} /> : <span aria-hidden="true">-</span>}
  </span>
);

// P7: design against code, and how far every requirement got. Computed by code only.
export function ConsistencyView({ report, busy, onOpenRequirement }: { report: Artifact } & Omit<Linking, "onOpenArtifact">) {
  const c = report.content;
  const rows: RequirementProgress[] = c.requirements ?? [];
  const drift: string[] = c.drift_lines ?? [];
  return (
    <section className="doc" aria-labelledby="consistency-heading">
      <header className="doc-head">
        <div>
          <h2 id="consistency-heading">Consistency</h2>
          <p className="meta">Computed by code, no model asked <span aria-hidden="true">·</span> check {report.revision}</p>
        </div>
      </header>
      <div className="verdict" data-ok={(c.in_sync && c.verified === c.total) || undefined} role="status">
        <Icon name={c.in_sync && c.verified === c.total ? "check" : "alert"} />
        <p>
          <strong>
            {c.in_sync === null ? "No class diagram to compare with." : c.in_sync ? "Design and code agree." : "Design and code disagree."}
          </strong>{" "}
          {c.verified} of {c.total} requirements are verified by passing tests.
        </p>
      </div>
      {drift.length > 0 && (
        <ul className="drift">
          {drift.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      )}
      {(c.hand_edited ?? []).length > 0 && <p className="doc-summary">Edited by hand: {(c.hand_edited as string[]).join(", ")}.</p>}
      {(c.stale ?? []).length > 0 && (
        <p className="notice" role="status">
          <Icon name="alert" size={14} /> Out of date: {(c.stale as string[]).join(", ")}.
        </p>
      )}
      <div className="matrix-wrap">
        <table className="progress-table">
          <thead>
            <tr>
              <th scope="col">Requirement</th>
              <th scope="col">Design</th>
              <th scope="col">Code</th>
              <th scope="col">Tests</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <th scope="row">
                  <button type="button" className="matrix-req" disabled={busy} onClick={() => onOpenRequirement(r.id)}>
                    <span className="req-id">{r.id}</span>
                    <span>{r.title}</span>
                  </button>
                </th>
                <td>{yes(r.design, "In a diagram")}</td>
                <td>{yes(r.code, "Implemented")}</td>
                <td>{yes(r.tests, "Tested")}</td>
                <td>
                  <span className="outcome" data-outcome={r.result ?? "none"}>
                    {r.result ? (VERDICT_LABEL[r.result] ?? r.result) : "not run"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
