import { useEffect, useRef, useState } from "react";
import type { Artifact, RequirementItem, Trace } from "../api/types";
import { authorName } from "../lib/format";
import { Icon } from "./Icon";

interface Props {
  artifact: Artifact;
  trace: Trace | null;
  focus: string | null; // requirement id to scroll to and highlight
  onOpenArtifact: (artifactId: string) => void;
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

export function RequirementsView({ artifact, trace, focus, onOpenArtifact, onSave }: Props) {
  const items = artifact.content.requirements as RequirementItem[];
  const assumptions = (artifact.content.assumptions as string[] | undefined) ?? [];
  const [draft, setDraft] = useState<RequirementItem[] | null>(null);
  const [saving, setSaving] = useState(false);
  const rows = draft ?? items;
  const untitled = draft?.some((r) => !r.title.trim()) ?? false;
  const list = useRef<HTMLOListElement>(null);

  useEffect(() => {
    if (!focus || !list.current) return;
    list.current.querySelector<HTMLElement>(`[data-req="${focus}"]`)?.scrollIntoView({ block: "center" });
  }, [focus]);

  const change = (i: number, patch: Partial<RequirementItem>) => setDraft(rows.map((r, j) => (i === j ? { ...r, ...patch } : r)));
  const titleOf = (id: string) => trace?.artifacts.find((a) => a.id === id)?.title ?? id;
  const traced = (trace?.artifacts.length ?? 0) > 0;
  const quality = items.filter((r) => r.type === "non_functional").length;

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const clean = draft.map((r) => ({ ...r, acceptance_criteria: r.acceptance_criteria.map((c) => c.trim()).filter(Boolean) }));
      await onSave({ ...artifact.content, requirements: clean });
      setDraft(null);
    } catch {
      // The app shows the error; the draft stays so nothing typed is lost.
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="doc" aria-labelledby="req-heading">
      <header className="doc-head">
        <div>
          <h2 id="req-heading">Requirements</h2>
          <p className="meta">
            Revision {artifact.revision} by {authorName(artifact.author)} <span aria-hidden="true">·</span>{" "}
            <span className="path">{artifact.path}</span>
          </p>
        </div>
        {draft ? (
          <div className="row-actions">
            <button type="button" className="button" onClick={() => setDraft(null)} disabled={saving}>
              Discard
            </button>
            <button type="button" className="button button-primary" onClick={save} disabled={saving || untitled}>
              Save as revision {artifact.revision + 1}
            </button>
          </div>
        ) : (
          <button type="button" className="button" onClick={() => setDraft(items.map((r) => ({ ...r })))}>
            <Icon name="pencil" size={14} />
            Edit
          </button>
        )}
      </header>

      <p className="doc-summary">{artifact.content.summary as string}</p>
      <p className="doc-count">
        {items.length} requirements, {items.length - quality} functional, {quality} quality
      </p>
      {untitled && (
        <p className="notice" role="status">
          Every requirement needs a title. Use Remove to delete one.
        </p>
      )}

      <ol className="req-list" ref={list}>
        {rows.map((r, i) => {
          const by = r.id ? trace?.covered[r.id] ?? [] : [];
          return (
            <li key={r.id || `new-${i}`} className="req" data-req={r.id || undefined} data-focus={focus === r.id || undefined}>
              <span className="req-id">{r.id || "new"}</span>
              {draft ? (
                <div className="req-edit">
                  <input aria-label={`Title of ${r.id || "new requirement"}`} value={r.title} placeholder="Title" onChange={(e) => change(i, { title: e.target.value })} />
                  <textarea
                    aria-label="Description"
                    rows={2}
                    placeholder="What the software does"
                    value={r.description}
                    onChange={(e) => change(i, { description: e.target.value })}
                  />
                  <textarea
                    aria-label="Acceptance criteria, one per line"
                    rows={Math.max(2, r.acceptance_criteria.length)}
                    placeholder="Acceptance criteria, one per line"
                    value={r.acceptance_criteria.join("\n")}
                    onChange={(e) => change(i, { acceptance_criteria: e.target.value.split("\n") })}
                    onBlur={() => change(i, { acceptance_criteria: r.acceptance_criteria.map((c) => c.trim()).filter(Boolean) })}
                  />
                  <div className="req-selects">
                    <select aria-label="Type" value={r.type} onChange={(e) => change(i, { type: e.target.value as RequirementItem["type"] })}>
                      <option value="functional">Functional</option>
                      <option value="non_functional">Quality</option>
                    </select>
                    <select aria-label="Priority" value={r.priority} onChange={(e) => change(i, { priority: e.target.value as RequirementItem["priority"] })}>
                      <option value="must">Must</option>
                      <option value="should">Should</option>
                      <option value="could">Could</option>
                    </select>
                    <button type="button" className="button button-quiet" onClick={() => setDraft(rows.filter((_, j) => j !== i))}>
                      Remove
                    </button>
                  </div>
                </div>
              ) : (
                <div className="req-body">
                  <p className="req-title">
                    {r.title}
                    <span className="tag" data-priority={r.priority}>
                      {r.priority}
                    </span>
                    {r.type === "non_functional" && <span className="tag">quality</span>}
                  </p>
                  <p className="req-desc">{r.description}</p>
                  {r.acceptance_criteria.length > 0 && (
                    <ul className="criteria" aria-label="Acceptance criteria">
                      {r.acceptance_criteria.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  )}
                  {traced && (
                    <p className="req-trace">
                      {by.length === 0 ? (
                        <span className="trace-missing">In no diagram yet</span>
                      ) : (
                        <>
                          <span className="trace-label">In</span>
                          {by.map((aid) => (
                            <button key={aid} type="button" className="link" onClick={() => onOpenArtifact(aid)}>
                              {titleOf(aid)}
                            </button>
                          ))}
                        </>
                      )}
                    </p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {draft && (
        <button type="button" className="button" onClick={() => setDraft([...rows, blank()])}>
          <Icon name="plus" size={14} />
          Add requirement
        </button>
      )}
      {assumptions.length > 0 && (
        <section className="assumptions" aria-labelledby="assumptions-heading">
          <h3 id="assumptions-heading">Assumptions the analyst made</h3>
          <ul>
            {assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
