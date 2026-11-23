import { useState } from "react";
import type { Artifact, Change, RequirementProgress } from "../api/types";
import { VERDICT_LABEL } from "../api/types";
import { CHANGE_KIND_LABEL, changeStepOf, receiptTotals, totalsText } from "../lib/changes";
import { ChangeReceipt } from "./ChangeTracker";
import { CheckedByCode } from "./CheckedByCode";
import { Icon } from "./Icon";

const PHASE_TITLE: Record<string, string> = {
  diagram: "Diagram",
  source_file: "Code",
  test_file: "Test",
  deployment_file: "Deployment",
};

interface Linking {
  busy: boolean;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase?: string) => void;
}

// P7, nothing asked yet: the three ways in, one line each. Each picks the right action; the check runs at once.
export function MaintenanceStart({ onChange, onBug, onCheck }: { onChange: () => void; onBug: () => void; onCheck?: () => void }) {
  return (
    <div className="conversation-empty">
      <div className="ways" role="group" aria-label="What to do in Maintenance">
        <button type="button" className="way" onClick={onChange}>
          <Icon name="pencil" />
          Request a change or a new requirement
        </button>
        <button type="button" className="way" onClick={onBug}>
          <Icon name="alert" />
          Report a bug
        </button>
        {onCheck && (
          <button type="button" className="way" onClick={onCheck}>
            <Icon name="code" />
            Check consistency
          </button>
        )}
      </div>
    </div>
  );
}

// Where a tracked change stands, in the words of the tracker.
function ChangeStateTag({ change }: { change: Change }) {
  if (change.state === "complete") {
    const done = totalsText(receiptTotals(change.receipt));
    return (
      <span className="change-state" data-state="complete">
        <Icon name="check" size={12} />
        Carried through{done ? `: ${done}` : ""}
      </span>
    );
  }
  if (change.state === "dropped")
    return (
      <span className="change-state" data-state="dropped">
        Dropped, never started
      </span>
    );
  return (
    <span className="change-state" data-state="open">
      In progress, step {changeStepOf(change.progress)}
    </span>
  );
}

// P7: every change request, newest first, as rows that open: what it touches (from the trace), the plan,
// and for a tracked change its receipt. `featured` is the change the tracker above already shows in full.
export function ChangesView({
  changes,
  tracked = [],
  featured = null,
  busy,
  onOpenRequirement,
  onOpenArtifact,
}: { changes: Artifact[]; tracked?: Change[]; featured?: number | null } & Linking) {
  const sorted = [...changes].sort((a, b) => (b.content.number ?? 0) - (a.content.number ?? 0));
  // Without tracking (an older backend) the newest change is open, as it was before there was a tracker.
  const [open, setOpen] = useState<Set<number>>(() => new Set(tracked.length === 0 && sorted[0] ? [Number(sorted[0].content.number)] : []));
  const toggle = (n: number) =>
    setOpen((cur) => {
      const next = new Set(cur);
      if (!next.delete(n)) next.add(n);
      return next;
    });
  return (
    <section className="doc" aria-labelledby="changes-heading">
      <header className="doc-head">
        <div>
          <h2 id="changes-heading">{sorted.length === 1 ? "Impact and plan" : "All changes"}</h2>
          <p className="meta">
            {changes.length} {changes.length === 1 ? "request" : "requests"} <span aria-hidden="true">·</span> what each touches: <CheckedByCode />
          </p>
        </div>
      </header>
      <ol className="changes">
        {sorted.map((ch) => {
          const c = ch.content;
          const number = Number(c.number);
          const impact: Record<string, { id: string; title: string; kind: string }[]> = c.impact ?? {};
          const track = tracked.find((t) => t.number === number);
          const shown = open.has(number);
          const bodyId = `change-${number}-details`;
          return (
            <li key={ch.id} className="change" data-open={shown || undefined}>
              <button type="button" className="change-toggle" aria-expanded={shown} aria-controls={bodyId} onClick={() => toggle(number)}>
                <Icon name="chevron" size={12} className={shown ? "chevron-open" : undefined} />
                <span className="req-id">#{c.number}</span>
                <span className="tag" data-kind={c.kind}>
                  {CHANGE_KIND_LABEL[c.kind] ?? c.kind}
                </span>
                <strong>{c.summary}</strong>
                {track && <ChangeStateTag change={track} />}
              </button>
              {shown && (
                <div className="change-body" id={bodyId}>
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
                  {track && track.state !== "dropped" && number !== featured && (
                    <ChangeReceipt change={track} busy={busy} onOpenArtifact={onOpenArtifact} headingId={`change-${number}-row-receipt`} />
                  )}
                </div>
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
          <p className="meta">
            <CheckedByCode /> <span aria-hidden="true">·</span> check {report.revision}
          </p>
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
