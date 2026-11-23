import { useEffect, useRef } from "react";
import type { Artifact, RunGuide } from "../api/types";
import { CheckedByCode } from "./CheckedByCode";
import { CopyButton } from "./CopyButton";
import { Icon } from "./Icon";

interface Props {
  guide: Artifact;
  folder: string | null; // the project's folder on the developer's computer
  focus?: object | null; // changes whenever "Run it" was pressed: scroll here and light up
  busy: boolean;
  onOpenFolder: () => void;
}

/** `cd` into the project folder. Double quotes work in PowerShell, cmd and bash alike. */
export const cdCommand = (folder: string) => `cd "${folder}"`;

/** What "Copy all" puts on the clipboard: into the folder, then start. One command per line. */
export function runSequence(folder: string | null, start: string): string {
  return [folder ? cdCommand(folder) : null, start].filter(Boolean).join("\n");
}

function Line({ command, what }: { command: string; what: string }) {
  return (
    <li className="term-line">
      <span className="term-prompt" aria-hidden="true">
        &gt;
      </span>
      <code>{command}</code>
      <CopyButton text={command} describe={`Copy: ${what}`} />
    </li>
  );
}

// P6: how to start the program, with commands to paste into a terminal. The guide is data from the
// deployment wing; the folder comes from the project, so the first line is the real path.
export function RunGuideView({ guide, folder, focus, busy, onOpenFolder }: Props) {
  const c = guide.content as Partial<RunGuide>;
  const start = (c.start_command ?? "").trim();
  const examples = (c.example_commands ?? []).filter((e) => e.trim());
  const stop = (c.stop_hint ?? "").trim();
  const box = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!focus || !box.current) return;
    box.current.scrollIntoView?.({ block: "start" });
    box.current.focus({ preventScroll: true });
  }, [focus]);

  return (
    <section className="doc run" aria-labelledby="run-heading" ref={box} tabIndex={-1} data-focus={focus ? true : undefined}>
      <header className="doc-head">
        <div>
          <h2 id="run-heading">Run it</h2>
          <p className="meta">
            {c.checked ? (
              <>
                <CheckedByCode /> <span aria-hidden="true">·</span> the deployment check started exactly this program
              </>
            ) : (
              <span className="run-unchecked">Not checked: the deployment check did not start this command</span>
            )}
          </p>
        </div>
        {start && folder && <CopyButton className="button copy-button" text={runSequence(folder, start)} label="Copy all" describe="Copy all: go to the folder and start" />}
      </header>

      {!folder && (
        <p className="notice" role="status">
          <Icon name="folder" size={14} />
          <span>This project has no folder yet, so there is no place to run it from.</span>
          <button type="button" className="button" disabled={busy} onClick={onOpenFolder}>
            Choose a folder
          </button>
        </p>
      )}

      {start ? (
        <ol className="term" aria-label="Commands to start the program">
          {folder && <Line command={cdCommand(folder)} what="go to the project folder" />}
          <Line command={start} what="start the program" />
        </ol>
      ) : (
        <p className="run-none">No start command is known for this program. Ask the deployer for one with Revise.</p>
      )}

      {c.url && (
        <p className="run-note">
          Then open{" "}
          <a className="run-url" href={c.url} target="_blank" rel="noreferrer">
            {c.url}
            <Icon name="external" size={14} />
          </a>{" "}
          in a new tab. The program must be running first.
        </p>
      )}
      {stop && <p className="run-note">To stop it: {stop}</p>}

      {examples.length > 0 && (
        <div className="run-examples">
          <h3 id="run-examples-heading">Example commands</h3>
          <ul className="term" aria-labelledby="run-examples-heading">
            {examples.map((e) => (
              <Line key={e} command={e} what={e} />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
