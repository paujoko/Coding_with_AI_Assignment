import { useState } from "react";
import type { PickedFolder } from "../api/types";
import { Icon } from "./Icon";

interface Props {
  value: string;
  onChange: (path: string) => void;
  label: string;
  help: string;
  autoFocus?: boolean;
  // Opens Explorer or Finder on this computer (the backend runs here); missing when that is not possible.
  onBrowse?: (start: string) => Promise<PickedFolder | null>;
}

// A browser never tells a page the full path of a folder, so the backend opens the operating system's own
// dialog and sends the chosen path back (ADR 0015). Typing or pasting the path always works too.
export function FolderField({ value, onChange, label, help, autoFocus, onBrowse }: Props) {
  const [waiting, setWaiting] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const browse = async () => {
    if (!onBrowse) return;
    setWaiting(true);
    setNote(null);
    try {
      const picked = await onBrowse(value);
      if (!picked?.path) return;
      if (picked.suggested) {
        onChange(picked.suggested);
        setNote(`${picked.path} already has files, so Wings will create a new folder inside it. Change the name if you like.`);
      } else {
        onChange(picked.path);
      }
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setWaiting(false);
    }
  };
  return (
    <div className="field">
      <label className="field-label" htmlFor="folder-path">
        {label}
      </label>
      <div className="folder-field">
        <input
          id="folder-path"
          value={value}
          spellCheck={false}
          autoFocus={autoFocus}
          placeholder={"C:\\Projects\\todo-app"}
          onChange={(e) => {
            onChange(e.target.value);
            setNote(null);
          }}
        />
        {onBrowse && (
          <button type="button" className="button" onClick={browse} disabled={waiting}>
            <Icon name={waiting ? "spinner" : "folder"} size={14} className={waiting ? "spin" : undefined} />
            {waiting ? "Choose in the window that opened" : "Browse…"}
          </button>
        )}
      </div>
      {note && (
        <span className="field-help folder-field-note" role="status">
          {note}
        </span>
      )}
      <span className="field-help">{help}</span>
    </div>
  );
}
