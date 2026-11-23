import type { Change, ChangePhase, OpenChange, ReceiptPhase } from "../api/types";
import {
  artifactKindLabel,
  CHANGE_KIND_LABEL,
  type CarryRun,
  changeStepOf,
  duration,
  nextLabel,
  phaseObject,
  receiptRows,
  receiptTotals,
  totalsText,
} from "../lib/changes";
import { clock } from "../lib/format";
import { CheckedByCode } from "./CheckedByCode";
import { useElapsed } from "./Conversation";
import { Icon } from "./Icon";

interface Linking {
  busy: boolean;
  onOpenPhase: (phase: string) => void;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase: string) => void;
}

interface Props extends Linking {
  change: Change;
  run: CarryRun | null; // the run started from this tracker, while it works and after it stopped
  onAdvance: (change: Change, through: boolean) => void; // one step, or "Carry it through"
  onStop: () => void; // stop after the running step
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

function Elapsed({ since }: { since: string }) {
  const elapsed = useElapsed(since);
  return elapsed ? (
    <span className="progress-time" title="Real models can take several minutes for code and tests">
      {elapsed}
    </span>
  ) : null;
}

// What one finished call did, in plain words.
function stepSentence(step: CarryRun["steps"][number], through: boolean): string {
  const what = phaseObject(step.phase, step.title);
  const made = step.ran.length > 0;
  if (made && step.approved) return `Updated ${what}. Wings approved it: its code checks pass.`;
  if (made) return `Updated ${what}. Not approved yet.`;
  if (step.approved) return through ? `Wings approved ${what}: its code checks pass.` : `Approved ${what}.`;
  return `Nothing ran in ${step.title}.`;
}

// One change carried through the phases: the request, the six steps, the next step as one button,
// "Carry it through" with live progress, and the receipt. The one bold element of the Maintenance screen.
export function ChangeTracker({ change, run, busy, onAdvance, onStop, onOpenPhase, onOpenRequirement, onOpenArtifact }: Props) {
  const mine = run && run.change === change.number ? run : null;
  const active = mine?.active ?? false;
  const next = change.state === "open" ? change.next : null;
  const { progress } = change;
  const headingId = `change-${change.number}-heading`;
  const receiptOf = (phase: string) => change.receipt.find((r) => r.phase === phase);
  const stopNote = mine && !active && mine.stopped && mine.stopped !== next?.reason ? mine.stopped : null;
  const stopPhase = mine?.stoppedPhase ? progress.phases.find((p) => p.phase === mine.stoppedPhase) : undefined;
  const canRun = next?.kind === "run" || next?.kind === "approve";

  return (
    <section className="tracker" id="change-tracker" data-state={change.state} aria-labelledby={headingId} tabIndex={-1}>
      <header className="tracker-head">
        <h2 id={headingId}>Change #{change.number}</h2>
        <span className="tag" data-kind={change.kind}>
          {CHANGE_KIND_LABEL[change.kind] ?? change.kind}
        </span>
        {change.state === "open" && (
          <span className="badge tracker-state" data-status="ready">
            <span className="badge-dot" aria-hidden="true" />
            Step {changeStepOf(progress)}
          </span>
        )}
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

      {change.state === "open" && (
        <ol className="track" aria-label="Steps of this change" style={{ "--track-steps": Math.max(progress.phases.length, 1) } as React.CSSProperties}>
          {progress.phases.map((p) => {
            const running = active && mine?.current?.phase === p.phase;
            const receipt = receiptOf(p.phase);
            const touched = receipt ? receiptTotals([receipt]) : null;
            const meta = touched ? totalsText(touched) || (touched.identical ? "identical" : "") : "";
            return (
              <li key={p.phase} data-state={p.state} data-status={p.status} data-running={running || undefined}>
                <button
                  type="button"
                  className="track-step"
                  disabled={busy}
                  aria-current={p.state === "current" ? "step" : undefined}
                  title={`Open ${p.title}`}
                  onClick={() => onOpenPhase(p.phase)}
                >
                  <span className="track-icon" aria-hidden="true">
                    <TrackIcon phase={p} running={running} />
                  </span>
                  <span className="track-title">{p.title}</span>
                  <span className="track-word">{running ? "Running" : STATE_WORD[p.state]}</span>
                  {meta && <span className="track-meta">{meta}</span>}
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {next && !active && (
        <div className="tracker-next" data-kind={next.kind}>
          {(next.kind === "input" || next.kind === "blocked") && next.reason && (
            <p className="tracker-reason" role="status">
              <Icon name="alert" size={14} />
              <span>{next.reason}</span>
            </p>
          )}
          {mine?.failed && (
            <p className="tracker-reason" data-tone="error" role="alert">
              <Icon name="alert" size={14} />
              <span>That step did not run. {mine.failed}</span>
            </p>
          )}
          {stopNote && (
            <p className="tracker-reason" role="status">
              <Icon name="alert" size={14} />
              <span>{stopNote}</span>
              {stopPhase && canRun && (
                <button type="button" className="link" disabled={busy} onClick={() => onOpenPhase(stopPhase.phase)}>
                  Open {stopPhase.title}
                </button>
              )}
            </p>
          )}
          <div className="tracker-buttons">
            {canRun ? (
              <button
                type="button"
                className="button button-primary"
                disabled={busy}
                title={next.kind === "run" && next.steps.length > 0 ? `Runs ${next.steps.map((s) => s.label || s.action).join(", then ")} in ${next.title}. You approve afterwards.` : undefined}
                onClick={() => onAdvance(change, false)}
              >
                {next.kind === "approve" && <Icon name="check" size={14} />}
                {nextLabel(next)}
              </button>
            ) : (
              <button type="button" className="button button-primary" disabled={busy} onClick={() => onOpenPhase(next.phase)}>
                {nextLabel(next)}
                <Icon name="arrowRight" size={14} />
              </button>
            )}
            {next.kind === "approve" && (
              <button type="button" className="button" disabled={busy} onClick={() => onOpenPhase(next.phase)}>
                Look at {phaseObject(next.phase, next.title)}
              </button>
            )}
            {canRun && (
              <button type="button" className="button" disabled={busy} onClick={() => onAdvance(change, true)}>
                Carry it through
              </button>
            )}
          </div>
          {canRun && <p className="tracker-note">Carry it through runs every remaining step and approves each one whose code checks pass. It stops at questions and failed checks.</p>}
        </div>
      )}

      {mine && (active || mine.steps.length > 0) && change.state === "open" && (
        <div className="tracker-run" aria-live="polite">
          <ol className="carry-log" aria-label={mine.through ? "Carrying it through" : "This step"}>
            {mine.steps.map((s, i) => (
              <li key={`${s.phase}-${i}`} className="carry-done">
                <Icon name="check" size={14} />
                <span>{stepSentence(s, mine.through)}</span>
                <span className="progress-time">{duration(s.seconds)}</span>
              </li>
            ))}
            {mine.current && (
              <li className="carry-now">
                <Icon name="spinner" size={14} className="spin" />
                <span className="shimmer">{mine.current.doing}</span>
                <Elapsed since={mine.current.since} />
              </li>
            )}
          </ol>
          {active && mine.through && (
            <button type="button" className="button" aria-pressed={mine.stopping} disabled={mine.stopping} onClick={onStop}>
              {mine.stopping ? "Stops after this step" : "Stop after this step"}
            </button>
          )}
        </div>
      )}

      {change.state !== "dropped" && <ChangeReceipt change={change} busy={busy} onOpenArtifact={onOpenArtifact} headingId={`change-${change.number}-receipt`} />}
    </section>
  );
}

// In the dock of Maintenance while a change is open: one line that points at the tracker instead of an approval prompt.
export function ChangeDockNote({ open, nextTitle, onShow }: { open: OpenChange; nextTitle: string | null; onShow: () => void }) {
  return (
    <div className="next" data-status="change">
      <Icon name="refresh" />
      <p>
        <strong>
          Change #{open.number} is at step {changeStepOf(open)}.
        </strong>
        {nextTitle ? ` Next: ${nextTitle}.` : ""}
      </p>
      <div className="next-actions">
        <button type="button" className="button" onClick={onShow}>
          Show the change
        </button>
      </div>
    </div>
  );
}
