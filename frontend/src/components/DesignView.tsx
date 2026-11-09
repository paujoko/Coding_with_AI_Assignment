import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Artifact, Trace } from "../api/types";
import { authorName } from "../lib/format";
import { Icon } from "./Icon";

interface Props {
  projectId: string;
  diagrams: Artifact[]; // already in reading order
  trace: Trace | null;
  canRender: boolean;
  focus: string | null; // artifact id to open
  onOpenRequirement: (id: string) => void;
  onOpenTrace: () => void;
  onSave: (artifactId: string, text: string) => Promise<void>;
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

export function DesignView({ projectId, diagrams, trace, canRender, focus, onOpenRequirement, onOpenTrace, onSave }: Props) {
  const [openId, setOpenId] = useState<string | null>(focus);
  useEffect(() => {
    if (focus) setOpenId(focus);
  }, [focus]);
  const current = diagrams.find((d) => d.id === openId) ?? diagrams[0];
  const total = trace ? Object.keys(trace.covered).length + trace.uncovered.length : 0;

  return (
    <section className="doc" aria-labelledby="design-heading">
      <header className="doc-head">
        <div>
          <h2 id="design-heading">Design</h2>
          <p className="meta">{diagrams.length} diagrams in PlantUML</p>
        </div>
        {trace && total > 0 && (
          <button type="button" className="coverage" data-complete={trace.uncovered.length === 0} onClick={onOpenTrace}>
            <span className="coverage-meter" aria-hidden="true">
              <span style={{ width: `${Math.round(trace.ratio * 100)}%` }} />
            </span>
            {trace.uncovered.length === 0
              ? `All ${total} requirements covered`
              : `${trace.uncovered.length} of ${total} requirements in no diagram`}
            <Icon name="arrowRight" size={14} />
          </button>
        )}
      </header>
      {trace && trace.unknown_refs.length > 0 && (
        <p className="notice" role="status">
          Diagrams refer to requirements that do not exist: {trace.unknown_refs.join(", ")}.
        </p>
      )}

      <div className="tabs" role="tablist" aria-label="Diagrams">
        {diagrams.map((d) => (
          <button key={d.id} type="button" role="tab" aria-selected={d.id === current?.id} onClick={() => setOpenId(d.id)}>
            {d.title}
          </button>
        ))}
      </div>
      {current && (
        <Diagram
          key={`${current.id}-${current.revision}`}
          projectId={projectId}
          artifact={current}
          canRender={canRender}
          onOpenRequirement={onOpenRequirement}
          onSave={(t) => onSave(current.id, t)}
        />
      )}
    </section>
  );
}

function Diagram(p: {
  projectId: string;
  artifact: Artifact;
  canRender: boolean;
  onOpenRequirement: (id: string) => void;
  onSave: (text: string) => Promise<void>;
}) {
  const { artifact } = p;
  const [mode, setMode] = useState<"picture" | "source">(p.canRender ? "picture" : "source");
  const [draft, setDraft] = useState<string | null>(null);
  const [broken, setBroken] = useState(false);
  const [saving, setSaving] = useState(false);
  const svg = api.svgUrl(p.projectId, artifact.id, artifact.revision);
  const source = draft ?? artifact.text ?? "";

  const save = async () => {
    if (draft === null) return;
    setSaving(true);
    try {
      await p.onSave(draft);
      setDraft(null);
    } catch {
      // The app shows the error; the edited source stays in the editor.
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="diagram" role="tabpanel" aria-label={artifact.title}>
      <div className="diagram-bar">
        <p className="meta">
          {KIND_LABEL[artifact.content.kind] ?? artifact.content.kind} <span aria-hidden="true">·</span> revision {artifact.revision} by{" "}
          {authorName(artifact.author)}
        </p>
        <div className="segmented" role="group" aria-label="Show as">
          <button type="button" aria-pressed={mode === "picture"} onClick={() => setMode("picture")} disabled={!p.canRender}>
            <Icon name="image" size={14} />
            Picture
          </button>
          <button type="button" aria-pressed={mode === "source"} onClick={() => setMode("source")}>
            <Icon name="code" size={14} />
            Source
          </button>
        </div>
      </div>
      {artifact.covers.length > 0 && (
        <p className="covers">
          <span className="trace-label">Covers</span>
          {artifact.covers.map((c) => (
            <button key={c} type="button" className="req-chip" onClick={() => p.onOpenRequirement(c)}>
              {c}
            </button>
          ))}
        </p>
      )}
      {mode === "picture" && p.canRender && !broken ? (
        <a className="diagram-canvas" href={svg} target="_blank" rel="noreferrer" title="Open full size">
          <img src={svg} alt={`${artifact.title}, rendered from PlantUML`} onError={() => setBroken(true)} />
        </a>
      ) : (
        <div className="source">
          {broken && (
            <p className="notice" role="status">
              The renderer could not draw this diagram. Check the PlantUML source below.
            </p>
          )}
          <textarea
            className="code"
            aria-label={`PlantUML source of ${artifact.title}`}
            spellCheck={false}
            value={source}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.min(28, source.split("\n").length + 1)}
          />
          {draft !== null && (
            <div className="row-actions">
              <button type="button" className="button" onClick={() => setDraft(null)} disabled={saving}>
                Discard
              </button>
              <button type="button" className="button button-primary" onClick={save} disabled={saving}>
                Save as revision {artifact.revision + 1}
              </button>
            </div>
          )}
        </div>
      )}
      {artifact.content.rationale && (
        <div className="rationale">
          <h3>Why it looks like this</h3>
          <p>{artifact.content.rationale}</p>
        </div>
      )}
    </article>
  );
}
