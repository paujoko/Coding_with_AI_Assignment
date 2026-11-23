import { useEffect, useState } from "react";
import type { Artifact, Finding } from "../api/types";
import { CheckedByCode } from "./CheckedByCode";
import { Icon } from "./Icon";

interface Props {
  review: Artifact;
  canRun: boolean;
  busy: boolean;
  onApply: (findings: string[]) => void;
  onPicked?: (findings: string[]) => void; // the step screen carries the Apply button: it needs to know what is ticked
}

const SEVERITY_ORDER: Record<Finding["severity"], number> = { high: 0, medium: 1, low: 2 };

// P3: the reviewer's findings, like review comments on a pull request. Pick the ones to apply.
export function ReviewView({ review, canRun, busy, onApply, onPicked }: Props) {
  const findings = [...((review.content.findings ?? []) as Finding[])].sort(
    (a, b) => Number(a.status === "applied") - Number(b.status === "applied") || SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );
  const open = findings.filter((f) => f.status === "open");
  const [chosen, setChosen] = useState<Set<string>>(() => new Set(open.filter((f) => f.severity !== "low").map((f) => f.id)));
  const toggle = (id: string) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChosen(next);
  };
  const picked = open.filter((f) => chosen.has(f.id)).map((f) => f.id);
  const pickedKey = picked.join(",");
  useEffect(() => onPicked?.(picked), [pickedKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="doc" aria-labelledby="review-heading">
      <header className="doc-head">
        <div>
          <h2 id="review-heading">Review</h2>
          <p className="meta">
            {open.length} open, {findings.length - open.length} applied <span aria-hidden="true">·</span> revision {review.revision}
          </p>
        </div>
        {open.length > 0 && canRun && !onPicked && (
          <button type="button" className="button" disabled={busy || picked.length === 0} onClick={() => onApply(picked)}>
            <Icon name="check" size={14} />
            {picked.length === 0 ? "Pick findings to apply" : `Apply ${picked.length} ${picked.length === 1 ? "finding" : "findings"}`}
          </button>
        )}
      </header>
      {review.content.summary && <p className="doc-summary">{review.content.summary}</p>}
      {findings.length === 0 ? (
        <p className="empty-note">No findings. The design can be accepted as it is.</p>
      ) : (
        <ul className="findings">
          {findings.map((f) => {
            const applied = f.status === "applied";
            return (
              <li key={f.id} className="finding" data-applied={applied || undefined}>
                <label className="finding-pick">
                  <input
                    type="checkbox"
                    checked={applied || chosen.has(f.id)}
                    disabled={applied || busy || !canRun}
                    onChange={() => toggle(f.id)}
                    aria-label={`Apply ${f.id}`}
                  />
                </label>
                <div className="finding-body">
                  <p className="finding-head">
                    <span className="req-id">{f.id}</span>
                    <span className="tag" data-severity={f.severity}>
                      {f.severity}
                    </span>
                    <span className="finding-where">{f.diagram}</span>
                    {f.source === "check" && <CheckedByCode />}
                    {applied && (
                      <span className="tag" data-ok>
                        applied
                      </span>
                    )}
                  </p>
                  <p>{f.finding}</p>
                  <p className="finding-suggestion">
                    <span className="trace-label">Suggestion</span> {f.suggestion}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
