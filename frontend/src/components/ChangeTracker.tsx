import type { Change, ChangePhase, ReceiptPhase } from "../api/types";
import { artifactKindLabel, CHANGE_KIND_LABEL, receiptRows, receiptTotals, totalsText } from "../lib/changes";
import { clock } from "../lib/format";
import { CheckedByCode } from "./CheckedByCode";
import { Icon } from "./Icon";

interface Linking {
  busy: boolean;
  onOpenPhase: (phase: string) => void;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase: string) => void;
}

interface Props extends Linking {
  change: Change;
  running: boolean; // an update or a change step is running: only then the full track is shown
  activePhase: string | null; // the phase being updated right now
}

const STATE_WORD: Record<ChangePhase["state"], string> = { done: "Done", current: "Now", waiting: "Waiting", untouched: "Not affected" };

// The receipt: per phase the artifacts a change updated, added or removed, computed from revisions.
// This is the answer to "which artifacts were updated", so it stays a plain list that can be read from the back row.
export function ChangeReceipt({ change, busy, onOpenArtifact, headingId }: { change: Change; headingId: string } & Pick<Linking, "busy" | "onOpenArtifact">) {
  const totals = receiptTotals(change.receipt);
  const touched = change.receipt.filter((r) => r.updated.length + r.added.length + r.removed.length > 0);
  const rest = change.receipt.filter((r) => !touched.includes(r));
  const summary = totalsText(totals);
  return (
    <section className="receipt" aria-labelledby={headingId}>
      <header className="receipt-head">
        <h3 id={headingId}>What this change updated</h3>
        <CheckedByCode />
        {summary && (
          <p className="receipt-total">
            {summary} in {totals.phases} {totals.phases === 1 ? "step" : "steps"}
          </p>
        )}
      </header>
      {touched.length === 0 ? (
        <p className="receipt-none">Nothing updated yet.</p>
      ) : (
        <ol className="receipt-phases">
          {touched.map((r) => (
            <ReceiptGroup key={r.phase} group={r} busy={busy} onOpenArtifact={onOpenArtifact} />
          ))}
        </ol>
      )}
      {touched.length > 0 && rest.length > 0 && (
        <p className="receipt-none">
          {change.state === "open" ? "Nothing so far in" : "Nothing changed in"} {rest.map((r) => r.title).join(", ")}.
        </p>
      )}
    </section>
  );
}

function ReceiptGroup({ group, busy, onOpenArtifact }: { group: ReceiptPhase } & Pick<Linking, "busy" | "onOpenArtifact">) {
  const rows = receiptRows(group);
  return (
    <li className="receipt-phase">
      <h4>{group.title}</h4>
      <ul className="receipt-rows">
        {rows.map((e) => (
          <li key={`${e.what}-${e.id}`} className="receipt-row" data-what={e.what}>
            <span className="receipt-name">
              {e.what === "removed" ? (
                <span title={e.path ?? undefined}>{e.title}</span>
              ) : (
                <button type="button" className="link" disabled={busy} title={e.path ?? undefined} onClick={() => onOpenArtifact(e.id, group.phase)}>
                  {e.title}
                </button>
              )}
              <span className="receipt-kind">{artifactKindLabel(e.kind)}</span>
            </span>
            {e.what === "updated" && (
              <span className="receipt-rev">
                <span className="sr-only">
                  revision {e.before} to {e.after}
                </span>
                <span aria-hidden="true">
                  rev {e.before} <Icon name="arrowRight" size={12} /> <strong>{e.after}</strong>
                </span>
              </span>
            )}
            {e.what === "added" && (
              <span className="receipt-rev">
                <span className="tag" data-change="added">
                  new
                </span>
              </span>
            )}
            {e.what === "removed" && (
              <span className="receipt-rev">
                <span className="tag" data-change="deleted">
                  removed
                </span>
              </span>
            )}
            {e.what === "identical" && <span className="receipt-rev">rewritten, identical</span>}
          </li>
        ))}
      </ul>
    </li>
  );
}

function TrackIcon({ phase, running }: { phase: ChangePhase; running: boolean }) {
  if (running) return <Icon name="spinner" size={12} className="spin" />;
  if (phase.state === "done") return <Icon name="check" size={12} />;
  if (phase.state === "current" && phase.status === "stale") return <Icon name="alert" size={12} />;
  return null; // rings and dots are drawn by CSS, as in the sidebar checklist
}

// One change: the request, a compact progress line, and the receipt. The full list of steps shows only while an
// update runs; the next step and its button are the card above the input, not here.
export function ChangeTracker({ change, running, activePhase, busy, onOpenPhase, onOpenRequirement, onOpenArtifact }: Props) {
  const { progress } = change;
  const headingId = `change-${change.number}-heading`;
  const receiptOf = (phase: string) => change.receipt.find((r) => r.phase === phase);
  const total = Math.max(progress.total, 1);

  return (
    <section className="tracker" id="change-tracker" data-state={change.state} aria-labelledby={headingId} tabIndex={-1}>
      <header className="tracker-head">
        <h2 id={headingId}>Change #{change.number}</h2>
        <span className="tag" data-kind={change.kind}>
          {CHANGE_KIND_LABEL[change.kind] ?? change.kind}
        </span>
        {change.state === "complete" && (
          <span className="badge tracker-state" data-status="approved">
            <span className="badge-dot" aria-hidden="true" />
            Carried through{change.completed_at ? ` at ${clock(change.completed_at)}` : ""}
          </span>
        )}
        {change.state === "dropped" && <span className="badge tracker-state">Dropped</span>}
      </header>

      <blockquote className="tracker-request">{change.request || change.summary}</blockquote>
      {change.affected.length > 0 && (
        <p className="tracker-affects">
          <span>Affects</span>
          {change.affected.map((rid) => (
            <button key={rid} type="button" className="req-chip" disabled={busy} onClick={() => onOpenRequirement(rid)}>
              {rid}
            </button>
          ))}
        </p>
      )}

      {change.state === "dropped" && <p className="receipt-none">It was never started, and a newer change took its place.</p>}

      {change.state === "open" && !running && (
        <p className="tracker-line">
          <span className="tracker-bar" aria-hidden="true">
            <span style={{ width: `${Math.round((Math.min(progress.done, total) / total) * 100)}%` }} />
          </span>
          {progress.done} of {total} steps updated
        </p>
      )}

      {change.state === "open" && running && (
        <ol className="track" aria-label="Steps of this change" style={{ "--track-steps": Math.max(progress.phases.length, 1) } as React.CSSProperties}>
          {progress.phases.map((p) => {
            const now = activePhase === p.phase;
            const receipt = receiptOf(p.phase);
            const touched = receipt ? receiptTotals([receipt]) : null;
            const meta = touched ? totalsText(touched) || (touched.identical ? "identical" : "") : "";
            return (
              <li key={p.phase} data-state={now ? "current" : p.state} data-status={p.status} data-running={now || undefined}>
                <button type="button" className="track-step" disabled={busy} aria-current={now ? "step" : undefined} title={`Open ${p.title}`} onClick={() => onOpenPhase(p.phase)}>
                  <span className="track-icon" aria-hidden="true">
                    <TrackIcon phase={p} running={now} />
                  </span>
                  <span className="track-title">{p.title}</span>
                  <span className="track-word">{now ? "Running" : STATE_WORD[p.state]}</span>
                  {meta && <span className="track-meta">{meta}</span>}
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {change.state !== "dropped" && <ChangeReceipt change={change} busy={busy} onOpenArtifact={onOpenArtifact} headingId={`change-${change.number}-receipt`} />}
    </section>
  );
}
