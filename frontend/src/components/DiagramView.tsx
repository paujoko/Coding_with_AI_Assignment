import { useState } from "react";
import { api } from "../api/client";
import type { Artifact } from "../api/types";

interface Props {
  projectId: string;
  artifact: Artifact;
  canRender: boolean;
  onSave: (text: string) => Promise<void>;
}

const KIND_LABEL: Record<string, string> = {
  use_case: "Use case diagram",
  class: "Class diagram",
  sequence: "Sequence diagram",
  activity: "Activity diagram",
  component: "Component diagram",
  deployment: "Deployment diagram",
  state: "State diagram",
};

export function DiagramView({ projectId, artifact, canRender, onSave }: Props) {
  const [mode, setMode] = useState<"picture" | "source">(canRender ? "picture" : "source");
  const [draft, setDraft] = useState<string | null>(null);
  const [broken, setBroken] = useState(false);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (draft === null) return;
    setSaving(true);
    try {
      await onSave(draft);
      setDraft(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="diagram">
      <header className="artifact-head">
        <div>
          <h3>{artifact.title}</h3>
          <p className="meta">
            {KIND_LABEL[artifact.content.kind] ?? artifact.content.kind}, revision {artifact.revision} by {artifact.author}
          </p>
        </div>
        <div className="segmented" role="group" aria-label="View">
          <button type="button" aria-pressed={mode === "picture"} onClick={() => setMode("picture")} disabled={!canRender}>
            Picture
          </button>
          <button type="button" aria-pressed={mode === "source"} onClick={() => setMode("source")}>
            PlantUML
          </button>
        </div>
      </header>
      {artifact.covers.length > 0 && (
        <p className="covers">
          Covers{" "}
          {artifact.covers.map((c) => (
            <span key={c} className="tag">
              {c}
            </span>
          ))}
        </p>
      )}
      {mode === "picture" && canRender && !broken ? (
        <img
          className="diagram-img"
          src={api.svgUrl(projectId, artifact.id, artifact.revision)}
          alt={`${artifact.title}, rendered from PlantUML`}
          onError={() => setBroken(true)}
        />
      ) : (
        <div className="source">
          {broken && <p className="notice">The renderer could not draw this diagram. Check the PlantUML source.</p>}
          <textarea
            aria-label={`PlantUML source of ${artifact.title}`}
            spellCheck={false}
            value={draft ?? artifact.text ?? ""}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.min(24, (draft ?? artifact.text ?? "").split("\n").length + 1)}
          />
          {draft !== null && (
            <div className="row-actions">
              <button type="button" onClick={() => setDraft(null)} disabled={saving}>
                Discard
              </button>
              <button type="button" className="primary" onClick={save} disabled={saving}>
                Save as new revision
              </button>
            </div>
          )}
        </div>
      )}
      {artifact.content.rationale && <p className="rationale">{artifact.content.rationale}</p>}
    </article>
  );
}
