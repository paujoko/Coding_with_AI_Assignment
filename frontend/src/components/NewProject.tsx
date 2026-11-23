import { MODEL } from "./HowItWorks";
import { useCallback, useEffect, useRef, useState } from "react";
import { ACCEPT, formatSize, MAX_BYTES } from "../lib/attachments";
import type { PickedFolder } from "../api/types";
import { DropZone } from "./DropZone";
import { FolderField } from "./FolderField";
import { Icon } from "./Icon";
import { Mark } from "./Mark";

interface Props {
  busy: boolean;
  onCreate: (name: string, description: string, files: File[], folder: string) => Promise<boolean>;
  onBrowse?: (start: string, name: string) => Promise<PickedFolder | null>; // the operating system's folder dialog
  // Where a project with this name would be saved by default; null or a failure means "no suggestion".
  onSuggestFolder?: (name: string) => Promise<string | null>;
}

const SUGGEST_DELAY = 350; // ms without typing before the folder suggestion follows the description

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
export function NewProject({ busy, onCreate, onBrowse, onSuggestFolder }: Props) {
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [folder, setFolder] = useState("");
  const [own, setOwn] = useState(false); // the developer typed or browsed the folder: suggestions stop
  const [nudge, setNudge] = useState(false); // a start was tried without a folder
  const picker = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const tooBig = files.filter((f) => f.size > MAX_BYTES);
  const addFiles = useCallback((list: File[]) => setFiles((fs) => [...fs, ...list]), []);
  // A spec alone is enough to start: the project is then named after the first file.
  const name = description.trim()
    ? nameFrom(description)
    : files[0]
      ? nameFrom(files[0].name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " "))
      : nameFrom("");

  // The folder is prefilled with the backend's default for this project name and follows the description,
  // until the developer chooses a folder themselves. Without the endpoint the field stays as it is.
  useEffect(() => {
    if (own || !onSuggestFolder) return;
    let stale = false;
    const id = window.setTimeout(
      () => {
        onSuggestFolder(name).then(
          (path) => {
            if (!stale && path) setFolder(path);
          },
          () => undefined,
        );
      },
      folder ? SUGGEST_DELAY : 0,
    );
    return () => {
      stale = true;
      window.clearTimeout(id);
    };
  }, [name, own, onSuggestFolder]); // eslint-disable-line react-hooks/exhaustive-deps

  const chooseFolder = (path: string) => {
    setOwn(true);
    setFolder(path);
    setNudge(false);
  };

  // What keeps the project from starting, said on the send button.
  const missing =
    tooBig.length > 0
      ? "Remove the files larger than 5 MB first"
      : description.trim() === "" && files.length === 0
        ? "Describe the software first"
        : folder.trim() === ""
          ? "Choose a project folder first"
          : null;
  const noFolder = missing !== null && folder.trim() === "" && tooBig.length === 0 && (description.trim() !== "" || files.length > 0);

  const submit = async () => {
    if (busy) return;
    if (missing) {
      if (noFolder) {
        setNudge(true);
        folderInput.current?.focus();
      }
      return;
    }
    const text = description.trim() || "Please read the attached documents.";
    if (await onCreate(name, text, files, folder.trim())) {
      setDescription("");
      setFiles([]);
      setFolder("");
      setOwn(false);
    }
  };

  return (
    <section className="home" aria-labelledby="home-heading">
      <DropZone enabled={!busy} onFiles={addFiles} />
      <Mark size={44} />
      <h1 id="home-heading">What do you want to build?</h1>
      <p className="home-model">{MODEL}</p>
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
            </div>
            {/* Not the disabled attribute: a click still has to say what is missing. */}
            <button
              type="submit"
              className="send"
              aria-label="Start"
              aria-disabled={busy || missing !== null}
              aria-describedby={nudge && noFolder ? "home-missing" : undefined}
              title={busy ? "Starting" : (missing ?? "Start (Enter)")}
            >
              <Icon name={busy ? "spinner" : "arrowUp"} className={busy ? "spin" : undefined} />
            </button>
          </div>
        </div>
        <FolderField
          ref={folderInput}
          row
          value={folder}
          onChange={chooseFolder}
          label="Project folder"
          onBrowse={onBrowse ? (start) => onBrowse(start, name) : undefined}
        />
        {nudge && noFolder && (
          <p id="home-missing" className="home-missing" role="status">
            Choose a project folder to start.
          </p>
        )}
      </form>
      <div className="examples" role="group" aria-label="Examples">
        {EXAMPLES.map((e) => (
          <button key={e} type="button" className="example" onClick={() => setDescription(e)}>
            {e}
          </button>
        ))}
      </div>
    </section>
  );
}
