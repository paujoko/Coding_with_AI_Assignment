import { useEffect, useState } from "react";
import type { Artifact } from "../api/types";
import { authorName, downloadText } from "../lib/format";
import { Covers } from "./Covers";
import { Icon } from "./Icon";

interface Props {
  title: string; // "Code", "Tests", "Deployment files"
  summary: string;
  files: Artifact[];
  focus: string | null;
  busy: boolean;
  editable: boolean;
  onOpenRequirement: (id: string) => void;
  onSave: (artifactId: string, text: string) => Promise<void>;
}

const fileName = (a: Artifact) => String(a.content.path ?? a.path ?? a.id);

// P4 to P6: generated files as a list (like the files of a pull request); one is open below.
export function FilesView({ title, summary, files, focus, busy, editable, onOpenRequirement, onSave }: Props) {
  const sorted = [...files].sort((a, b) => fileName(a).localeCompare(fileName(b)));
  const [openId, setOpenId] = useState<string | null>(focus);
  useEffect(() => {
    if (focus && files.some((f) => f.id === focus)) setOpenId(focus);
  }, [focus]); // eslint-disable-line react-hooks/exhaustive-deps
  // Open the chosen file, else the first that implements a requirement (not an empty package marker).
  const current = sorted.find((f) => f.id === openId) ?? sorted.find((f) => f.covers.length > 0) ?? sorted[0];
  const slug = title.toLowerCase().replace(/\s+/g, "-");

  return (
    <section className="doc" aria-labelledby={`${slug}-heading`}>
      <header className="doc-head">
        <div>
          <h2 id={`${slug}-heading`}>{title}</h2>
          <p className="meta">
            {files.length} {files.length === 1 ? "file" : "files"}, {files.reduce((n, f) => n + (f.text ?? "").split("\n").length, 0)} lines
          </p>
        </div>
        <button
          type="button"
          className="button"
          title="Download every file, each under its path, in one text file"
          onClick={() =>
            downloadText(`${slug}.txt`, sorted.map((f) => `# ===== ${fileName(f)} =====\n${f.text ?? ""}`).join("\n\n"))
          }
        >
          <Icon name="download" size={14} />
          Download all
        </button>
      </header>
      <p className="doc-summary">{summary}</p>
      <ul className="file-list" aria-label={`${title}: files`}>
        {sorted.map((f) => (
          <li key={f.id}>
            <button type="button" aria-pressed={f.id === current?.id} onClick={() => setOpenId(f.id)}>
              <Icon name={f.id === current?.id ? "chevron" : "file"} size={14} className={f.id === current?.id ? "chevron-open" : undefined} />
              <span className="file-path">{fileName(f)}</span>
              <span className="file-purpose">{f.content.purpose}</span>
              {f.author === "developer" && <span className="tag">edited</span>}
            </button>
          </li>
        ))}
      </ul>
      {current && (
        <FileViewer
          key={`${current.id}-${current.revision}`}
          file={current}
          busy={busy}
          editable={editable}
          onOpenRequirement={onOpenRequirement}
          onSave={(t) => onSave(current.id, t)}
        />
      )}
    </section>
  );
}

function FileViewer(p: { file: Artifact; busy: boolean; editable: boolean; onOpenRequirement: (id: string) => void; onSave: (text: string) => Promise<void> }) {
  const { file } = p;
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = file.text ?? "";
  const lines = text.split("\n");

  const save = async () => {
    if (draft === null) return;
    setSaving(true);
    try {
      await p.onSave(draft);
      setDraft(null);
    } catch {
      // The app shows the error; the edited text stays in the editor.
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="file" aria-label={fileName(file)}>
      <div className="file-bar">
        <p className="meta">
          <span className="file-path">{fileName(file)}</span> <span aria-hidden="true">·</span> revision {file.revision} by {authorName(file.author)}
        </p>
        <div className="diagram-tools">
          <button
            type="button"
            className="icon-button"
            aria-label={copied ? "Copied" : `Copy ${fileName(file)}`}
            title={copied ? "Copied" : "Copy"}
            onClick={() =>
              navigator.clipboard?.writeText(text).then(() => {
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1500);
              })
            }
          >
            <Icon name={copied ? "check" : "copy"} />
          </button>
          <button
            type="button"
            className="icon-button"
            aria-label={`Download ${fileName(file)}`}
            title="Download"
            onClick={() => downloadText(fileName(file).split("/").pop() ?? file.id, text)}
          >
            <Icon name="download" />
          </button>
          {p.editable && draft === null && (
            <button type="button" className="button" disabled={p.busy} onClick={() => setDraft(text)}>
              <Icon name="pencil" size={14} />
              Edit
            </button>
          )}
        </div>
      </div>
      <Covers ids={file.covers} label="Implements" busy={p.busy} onOpen={p.onOpenRequirement} />
      {draft === null ? (
        <pre className="listing" tabIndex={0} aria-label={`Contents of ${fileName(file)}`}>
          <code>
            {lines.map((line, i) => (
              <span key={i} className="listing-line">
                <span className="listing-no" aria-hidden="true">
                  {i + 1}
                </span>
                {line || " "}
                {"\n"}
              </span>
            ))}
          </code>
        </pre>
      ) : (
        <div className="source">
          <textarea
            className="code"
            aria-label={`Edit ${fileName(file)}`}
            spellCheck={false}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.min(30, draft.split("\n").length + 1)}
          />
          <div className="row-actions">
            <button type="button" className="button" onClick={() => setDraft(null)} disabled={saving}>
              Discard
            </button>
            <button type="button" className="button button-primary" onClick={save} disabled={saving || draft === text}>
              Save as revision {file.revision + 1}
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
