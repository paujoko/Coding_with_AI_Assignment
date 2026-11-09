import { useState } from "react";
import type { Artifact, RequirementItem } from "../api/types";

interface Props {
  artifact: Artifact;
  onSave: (content: Record<string, unknown>) => Promise<void>;
}

const blank = (): RequirementItem => ({
  id: "",
  title: "",
  description: "",
  type: "functional",
  priority: "must",
  acceptance_criteria: [],
});

export function RequirementsView({ artifact, onSave }: Props) {
  const items = artifact.content.requirements as RequirementItem[];
  const [draft, setDraft] = useState<RequirementItem[] | null>(null);
  const [saving, setSaving] = useState(false);
  const rows = draft ?? items;

  const change = (i: number, patch: Partial<RequirementItem>) =>
    setDraft(rows.map((r, j) => (i === j ? { ...r, ...patch } : r)));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await onSave({ ...artifact.content, requirements: draft.filter((r) => r.title.trim()) });
      setDraft(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="requirements">
      <header className="artifact-head">
        <div>
          <h3>Requirements</h3>
          <p className="meta">
            Revision {artifact.revision} by {artifact.author}, saved as {artifact.path}
          </p>
        </div>
        {draft ? (
          <div className="row-actions">
            <button type="button" onClick={() => setDraft(null)} disabled={saving}>
              Discard
            </button>
            <button type="button" className="primary" onClick={save} disabled={saving}>
              Save as new revision
            </button>
          </div>
        ) : (
          <button type="button" onClick={() => setDraft(items.map((r) => ({ ...r })))}>
            Edit
          </button>
        )}
      </header>
      <p className="summary">{artifact.content.summary as string}</p>
      <ol className="req-list">
        {rows.map((r, i) => (
          <li key={r.id || `new-${i}`} className="req" data-type={r.type}>
            <span className="req-id">{r.id || "new"}</span>
            {draft ? (
              <div className="req-edit">
                <input aria-label="Title" value={r.title} onChange={(e) => change(i, { title: e.target.value })} />
                <textarea
                  aria-label="Description"
                  rows={2}
                  value={r.description}
                  onChange={(e) => change(i, { description: e.target.value })}
                />
                <div className="req-selects">
                  <select aria-label="Type" value={r.type} onChange={(e) => change(i, { type: e.target.value as RequirementItem["type"] })}>
                    <option value="functional">functional</option>
                    <option value="non_functional">non-functional</option>
                  </select>
                  <select
                    aria-label="Priority"
                    value={r.priority}
                    onChange={(e) => change(i, { priority: e.target.value as RequirementItem["priority"] })}
                  >
                    <option value="must">must</option>
                    <option value="should">should</option>
                    <option value="could">could</option>
                  </select>
                  <button type="button" className="link" onClick={() => setDraft(rows.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <p className="req-title">
                  {r.title} <span className={`prio prio-${r.priority}`}>{r.priority}</span>
                  {r.type === "non_functional" && <span className="nfr">quality</span>}
                </p>
                <p className="req-desc">{r.description}</p>
                {r.acceptance_criteria.length > 0 && (
                  <ul className="criteria">
                    {r.acceptance_criteria.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>
      {draft && (
        <button type="button" onClick={() => setDraft([...rows, blank()])}>
          Add requirement
        </button>
      )}
      {(artifact.content.assumptions as string[] | undefined)?.length ? (
        <div className="assumptions">
          <h4>Assumptions the analyst made</h4>
          <ul>
            {(artifact.content.assumptions as string[]).map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
