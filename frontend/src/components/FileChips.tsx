import type { AttachmentRef } from "../api/types";
import { formatSize, type PendingFile } from "../lib/attachments";
import { Icon } from "./Icon";

/** Files waiting in the input, with upload state and a remove button. */
export function PendingChips({ files, onRemove }: { files: PendingFile[]; onRemove: (key: string) => void }) {
  if (files.length === 0) return null;
  return (
    <ul className="file-chips" aria-label="Attached files">
      {files.map((f) => (
        <li key={f.key} className="file-chip" data-status={f.status} title={f.error ?? `${f.name}, ${formatSize(f.size)}`}>
          <Icon name={f.status === "uploading" ? "spinner" : f.status === "error" ? "alert" : "file"} size={14} className={f.status === "uploading" ? "spin" : undefined} />
          <span className="file-chip-name">{f.name}</span>
          <span className="file-chip-meta">{f.status === "error" ? f.error : f.status === "uploading" ? "uploading" : formatSize(f.size)}</span>
          <button type="button" className="file-chip-remove" aria-label={`Remove ${f.name}`} onClick={() => onRemove(f.key)}>
            <Icon name="close" size={12} />
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Files a sent message referred to. */
export function SentChips({ refs }: { refs: AttachmentRef[] }) {
  return (
    <ul className="file-chips file-chips-sent" aria-label="Attached files">
      {refs.map((r) => (
        <li key={r.id} className="file-chip">
          <Icon name="file" size={14} />
          <span className="file-chip-name">{r.name}</span>
        </li>
      ))}
    </ul>
  );
}
