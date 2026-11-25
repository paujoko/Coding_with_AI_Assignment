import type { PhaseState } from "../api/types";
import type { UpdateRun } from "../lib/catchup";
import { stepTitle } from "../lib/flow";
import { Icon } from "./Icon";

interface Props {
  redo: string[]; // steps that have to follow a change, in order
  all: PhaseState[];
  busy: boolean;
  run: UpdateRun | null; // "Accept the rest when checks pass", live and after it stopped
  current: string | null; // the step on screen
  onRest: () => void; // redo all, accepting each step whose code checks pass
  onStop: () => void;
  onGo: (phase: string) => void;
}

// Shown on every step while a change is not through: which steps follow it, in order, and the one button for the
// next. The order is the backend's (`stale`, API 10); nothing here guesses.
export function RedoStrip(p: Props) {
  const r = p.run;
  if (r?.active) {
    const cur = r.current;
    return (
      <section className="redo-strip" aria-label="Redo" data-running>
        <Icon name="spinner" className="spin" />
        <p>
          <strong>Redoing {cur ? stepTitle({ id: cur.phase }) : "the next step"}</strong>
          <span className="redo-count">
            {" "}
            {cur?.index ?? r.steps.length + 1} of {Math.max(r.total, 1)}
          </span>
        </p>
        {!r.only && (
          <button type="button" className="button-link" disabled={r.stopping} onClick={p.onStop}>
            {r.stopping ? "Stops after this step" : "Stop"}
          </button>
        )}
      </section>
    );
  }
  const stopped = r && !r.active && (r.stopped || r.failed) ? (r.failed ?? r.stopped) : null;
  if (p.redo.length === 0 && !stopped) return null;
  const first = p.redo[0];
  return (
    <section className="redo-strip" aria-label="Redo after your change">
      <Icon name="refresh" />
      <div className="redo-main">
        {p.redo.length > 0 && (
          <p>
            <strong>Redo after your change:</strong>{" "}
            <span className="redo-order">
              {p.redo.map((id, i) => (
                <span key={id}>
                  {i > 0 && <span className="redo-sep" aria-hidden="true">{" › "}</span>}
                  <button type="button" className="redo-step" aria-current={p.current === id ? "step" : undefined} onClick={() => p.onGo(id)}>
                    {stepTitle(p.all.find((x) => x.id === id) ?? { id })}
                  </button>
                </span>
              ))}
            </span>
          </p>
        )}
        {stopped && <p className="redo-stopped">{stopped}</p>}
      </div>
      {first && (
        <div className="redo-actions">
          <button type="button" className="button-link" disabled={p.busy} title="Redoes each step in order and accepts it when its code checks pass. Stops at questions and failed checks." onClick={p.onRest}>
            Redo all, accept when checks pass
          </button>
          {/* The strip informs; the one primary button is on the screen below it ("Redo Design", "Accept and
              redo Design", "Continue with Design"). Two solid buttons on one screen was the confusion we removed. */}
        </div>
      )}
    </section>
  );
}
