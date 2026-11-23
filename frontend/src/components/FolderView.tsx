import { useEffect, useState } from "react";
import type { FolderChange, FolderImport, FolderStatus, PhaseState, PickedFolder } from "../api/types";
import { CheckedByCode } from "./CheckedByCode";
import { FolderField } from "./FolderField";
import { Icon } from "./Icon";

interface Props {
  status: FolderStatus | null;
  phases: PhaseState[];
  busy: boolean;
  result: FolderImport | null; // the last import, so its check against the design stays on screen
  onLink: (path: string) => Promise<boolean>;
  onUnlink: () => void;
  onImport: (paths: string[]) => void;
  onRestore: (paths: string[]) => void;
  onRefresh: () => void;
  onOpenPhase: (phase: string) => void;
  onBrowse?: (start: string) => Promise<PickedFolder | null>; // the operating system's folder dialog
}

const CHANGE_LABEL: Record<FolderChange["change"], string> = { modified: "changed", added: "new", deleted: "deleted" };

// The project's folder on the developer's computer (ADR 0015). Wings writes to it after every step; the developer
// edits there in their own editor; what changed by hand is listed here and taken over only when they say so.
export function FolderView({ status, phases, busy, result, onLink, onUnlink, onImport, onRestore, onRefresh, onOpenPhase, onBrowse }: Props) {
  const [editing, setEditing] = useState(false);
  const changes = status?.changes ?? [];
  const importable = changes.filter((c) => c.importable).map((c) => c.path);
  const [picked, setPicked] = useState<string[]>(importable);
  const key = importable.join("|");
  useEffect(() => setPicked(key ? key.split("|") : []), [key]);
  const phaseTitle = (id: string | null) => phases.find((p) => p.id === id)?.title ?? "";

  const head = (
    <header className="page-head">
      <h1 id="folder-heading">Folder</h1>
      {!status?.path && <p className="lede">Choose where Wings saves this project's files.</p>}
    </header>
  );

  if (!status?.path || editing) {
    return (
      <section className="page folder-page" aria-labelledby="folder-heading">
        {head}
        <LinkForm
          current={status?.path ?? ""}
          busy={busy}
          onBrowse={onBrowse}
          onCancel={status?.path ? () => setEditing(false) : undefined}
          onLink={async (path) => {
            const ok = await onLink(path);
            if (ok) setEditing(false);
            return ok;
          }}
        />
      </section>
    );
  }

  return (
    <section className="page folder-page" aria-labelledby="folder-heading">
      {head}
      <div className="folder-path">
        <Icon name="folder" />
        <code title={status.path}>{status.path}</code>
        <div className="folder-path-actions">
          <button type="button" className="button button-quiet" onClick={() => navigator.clipboard?.writeText(status.path ?? "")} title="Copy the path">
            <Icon name="copy" size={14} />
            <span className="sr-only">Copy the path</span>
          </button>
          <button type="button" className="button" disabled={busy} onClick={() => setEditing(true)}>
            Change
          </button>
          <button type="button" className="button button-quiet" disabled={busy} onClick={onUnlink} title="Wings stops writing there; the files stay">
            Unlink
          </button>
        </div>
      </div>

      {status.problem && (
        <p className="notice" role="alert">
          <Icon name="alert" size={14} /> {status.problem}
        </p>
      )}

      {!status.problem && changes.length === 0 && (
        <p className="folder-sync" role="status">
          <Icon name="check" size={14} /> In sync with Wings. <CheckedByCode />
        </p>
      )}

      {changes.length > 0 && (
        <>
          <h2 className="folder-subhead">Changed in your folder</h2>
          <ul className="folder-changes">
            {changes.map((c) => (
              <li key={c.path} className="folder-change" data-importable={c.importable || undefined}>
                <label className="folder-change-pick">
                  <input
                    type="checkbox"
                    disabled={!c.importable || busy}
                    checked={c.importable && picked.includes(c.path)}
                    onChange={(e) => setPicked(e.target.checked ? [...picked, c.path] : picked.filter((p) => p !== c.path))}
                    aria-label={`Import ${c.path}`}
                  />
                  <code className="folder-change-path">{c.path}</code>
                </label>
                <span className="tag" data-change={c.change}>
                  {CHANGE_LABEL[c.change]}
                </span>
                {c.phase && <span className="folder-change-phase">{phaseTitle(c.phase)}</span>}
                <p className="folder-change-note">
                  {c.note}
                  {c.newer_in_wings && c.change !== "added" && " Wings has a newer version: importing replaces it, restoring drops your edit."}
                </p>
                {c.change !== "added" && (
                  <button type="button" className="button button-quiet" disabled={busy} onClick={() => onRestore([c.path])}>
                    <Icon name="undo" size={14} /> Restore Wings' version
                  </button>
                )}
              </li>
            ))}
          </ul>
          <div className="settings-actions">
            <button type="button" className="button button-primary" disabled={busy || picked.length === 0} onClick={() => onImport(picked)}>
              Import {picked.length} into Wings
            </button>
            <button type="button" className="button" disabled={busy} onClick={onRefresh}>
              <Icon name="refresh" size={14} /> Check again
            </button>
          </div>
        </>
      )}

      {result && (
        <div className="folder-result" role="status">
          <h2 className="folder-subhead">Last import</h2>
          <p className="folder-result-text">{result.reply}</p>
          <div className="row-actions folder-result-actions">
            {Array.from(new Set(result.imported.map((c) => c.phase).filter((p): p is string => !!p))).map((p) => (
              <button key={p} type="button" className="button" disabled={busy} onClick={() => onOpenPhase(p)}>
                Open {phaseTitle(p)} <Icon name="arrowRight" size={14} />
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function LinkForm({
  current,
  busy,
  onLink,
  onCancel,
  onBrowse,
}: {
  current: string;
  busy: boolean;
  onLink: (path: string) => Promise<boolean>;
  onCancel?: () => void;
  onBrowse?: (start: string) => Promise<PickedFolder | null>;
}) {
  const [path, setPath] = useState(current);
  return (
    <form
      className="settings-form folder-link"
      onSubmit={(e) => {
        e.preventDefault();
        if (path.trim()) onLink(path.trim());
      }}
    >
      <FolderField
        value={path}
        onChange={setPath}
        label="Project folder"
        autoFocus
        onBrowse={onBrowse}
      />
      <div className="settings-actions">
        <button type="submit" className="button button-primary" disabled={busy || !path.trim()}>
          {busy ? "Linking" : "Use this folder"}
        </button>
        {onCancel && (
          <button type="button" className="button" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
