import { useCallback, useRef, useState } from "react";
import { ACCEPT, formatSize, MAX_BYTES } from "../lib/attachments";
import { DropZone } from "./DropZone";
import { Icon } from "./Icon";
import { Mark } from "./Mark";

interface Props {
  busy: boolean;
  onCreate: (name: string, description: string, files: File[]) => Promise<boolean>;
}

const EXAMPLES = [
  "A to-do app for a small team: tasks with a due date and someone assigned.",
  "A room booking tool for a student association, with a calendar per room.",
  "A command-line expense tracker that groups spending by month.",
];

// Words that start the "what for" part of a description; the name stops before them.
const STOP = new Set(["for", "with", "that", "which", "where", "who", "to", "in", "on", "so", "and"]);

/** A short project name from the description: the noun phrase it starts with, at most four words. */
export function nameFrom(description: string): string {
  const clause = description.trim().split(/[.,:;!?\n]/)[0] ?? "";
  const words: string[] = [];
  for (const w of clause
    .replace(/^(an?|the)\s+/i, "")
    .split(/\s+/)
    .filter(Boolean)) {
    if (words.length > 0 && STOP.has(w.toLowerCase())) break;
    words.push(w);
    if (words.length === 4) break;
  }
  const name = words.join(" ");
  return name ? name.charAt(0).toUpperCase() + name.slice(1) : "New project";
}

// The start page works like the start of a chat: say what you want, press Enter.
export function NewProject({ busy, onCreate }: Props) {
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const picker = useRef<HTMLInputElement>(null);
  const tooBig = files.filter((f) => f.size > MAX_BYTES);
  const ready = (description.trim() !== "" || files.length > 0) && tooBig.length === 0 && !busy;
  const addFiles = useCallback((list: File[]) => setFiles((fs) => [...fs, ...list]), []);

  const submit = async () => {
    if (!ready) return;
    // A spec alone is enough to start: the analyst reads it.
    const text = description.trim() || "Please read the attached documents.";
    const name = description.trim() ? nameFrom(description) : nameFrom(files[0].name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " "));
    if (await onCreate(name, text, files)) {
      setDescription("");
      setFiles([]);
    }
  };

  return (
    <section className="home" aria-labelledby="home-heading">
      <DropZone enabled={!busy} onFiles={addFiles} />
      <Mark size={44} />
      <h1 id="home-heading">What do you want to build?</h1>
      <form
        className="composer home-composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="composer-box">
          {files.length > 0 && (
            <ul className="file-chips" aria-label="Attached files">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`} className="file-chip" data-status={f.size > MAX_BYTES ? "error" : "ready"}>
                  <Icon name={f.size > MAX_BYTES ? "alert" : "file"} size={14} />
                  <span className="file-chip-name">{f.name}</span>
                  <span className="file-chip-meta">{f.size > MAX_BYTES ? "larger than 5 MB" : formatSize(f.size)}</span>
                  <button
                    type="button"
                    className="file-chip-remove"
                    aria-label={`Remove ${f.name}`}
                    onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  >
                    <Icon name="close" size={12} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <label className="field field-main">
            <span className="sr-only">Describe the software</span>
            <textarea
              rows={3}
              value={description}
              autoFocus
              placeholder="Describe the software in a few sentences, or attach a brief or spec"
              onChange={(e) => setDescription(e.target.value)}
              onPaste={(e) => {
                const pasted = Array.from(e.clipboardData.files);
                if (pasted.length) {
                  e.preventDefault();
                  addFiles(pasted);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
          </label>
          <div className="composer-bar">
            <div className="composer-tools">
              <input
                ref={picker}
                type="file"
                multiple
                accept={ACCEPT}
                hidden
                onChange={(e) => {
                  if (e.target.files?.length) addFiles(Array.from(e.target.files));
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                className="icon-button"
                aria-label="Attach documents"
                title="Attach documents (text, Markdown, PDF, Word)"
                onClick={() => picker.current?.click()}
              >
                <Icon name="paperclip" />
              </button>
              <span className="composer-note">Enter to start, Shift+Enter for a new line</span>
            </div>
            <button type="submit" className="send" aria-label="Start" disabled={!ready}>
              <Icon name={busy ? "spinner" : "arrowUp"} className={busy ? "spin" : undefined} />
            </button>
          </div>
        </div>
      </form>
      <div className="examples" role="group" aria-label="Examples">
        {EXAMPLES.map((e) => (
          <button key={e} type="button" className="example" onClick={() => setDescription(e)}>
            {e}
          </button>
        ))}
      </div>
      <p className="home-note">
        Agents turn your idea into requirements, design, code, tests and a deployment. After every step they wait for your approval.
      </p>
    </section>
  );
}
