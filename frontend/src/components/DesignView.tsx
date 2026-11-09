import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Artifact, Trace } from "../api/types";
import { authorName, downloadText } from "../lib/format";
import { Covers } from "./Covers";
import { Icon } from "./Icon";

interface Props {
  title?: string;
  projectId: string;
  diagrams: Artifact[]; // already in reading order
  trace: Trace | null;
  canRender: boolean;
  focus: string | null; // artifact id to open
  busy: boolean; // links to other views wait while an agent works
  onOpenRequirement: (id: string) => void;
  onOpenTrace: () => void;
  onSetupDiagrams: () => void;
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

export function DesignView({ title = "Design", projectId, diagrams, trace, canRender, focus, busy, onOpenRequirement, onOpenTrace, onSetupDiagrams, onSave }: Props) {
  const [openId, setOpenId] = useState<string | null>(focus);
  useEffect(() => {
    if (focus) setOpenId(focus);
  }, [focus]);
  const current = diagrams.find((d) => d.id === openId) ?? diagrams[0];
  const total = trace ? Object.keys(trace.covered).length + trace.uncovered.length : 0;

  return (
    <section className="doc" aria-labelledby="design-heading">
      <header className="doc-head">
        <h2 id="design-heading">{title}</h2>
        {trace && total > 0 && (
          <button type="button" className="coverage" data-complete={trace.uncovered.length === 0} disabled={busy} onClick={onOpenTrace}>
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

      <div className="tabs" role="group" aria-label="Diagrams">
        {diagrams.map((d) => (
          <button key={d.id} type="button" aria-pressed={d.id === current?.id} onClick={() => setOpenId(d.id)}>
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
          busy={busy}
          onSetupDiagrams={onSetupDiagrams}
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
  busy: boolean;
  onSetupDiagrams: () => void;
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
    <article className="diagram" aria-label={artifact.title}>
      <div className="diagram-bar">
        <p className="meta">
          {KIND_LABEL[artifact.content.kind] ?? artifact.content.kind} <span aria-hidden="true">·</span> revision {artifact.revision} by{" "}
          {authorName(artifact.author)}
        </p>
        <div className="diagram-tools">
          <button
            type="button"
            className="icon-button"
            aria-label={`Download ${artifact.path ?? "diagram.puml"}`}
            title={`Download the PlantUML source (${artifact.path?.split("/").pop() ?? "diagram.puml"})`}
            onClick={() => downloadText(artifact.path?.split("/").pop() ?? `${artifact.id}.puml`, artifact.text ?? "")}
          >
            <Icon name="download" />
          </button>
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
      </div>
      <Covers ids={artifact.covers} busy={p.busy} onOpen={p.onOpenRequirement} />
      {mode === "picture" && p.canRender && !broken ? (
        <a className="diagram-canvas" href={svg} target="_blank" rel="noreferrer" title="Open full size">
          <img src={svg} alt={`${artifact.title}, rendered from PlantUML`} onError={() => setBroken(true)} />
        </a>
      ) : (
        <div className="source">
          {!p.canRender && (
            <p className="notice notice-info" role="status">
              <Icon name="image" size={14} />
              <span>Pictures need PlantUML, which is not set up on this computer yet.</span>
              <button type="button" className="button" onClick={p.onSetupDiagrams}>
                Set up pictures
              </button>
            </p>
          )}
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
