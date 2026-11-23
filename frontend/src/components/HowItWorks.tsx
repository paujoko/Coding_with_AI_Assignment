import { useEffect, useRef } from "react";
import { ACTION_LABEL, ACTION_MEANING, type DisplayStatus } from "../lib/status";
import { Icon } from "./Icon";

// "planned" stays in the vocabulary for a future wing but is not explained while every wing is built.
const ORDER: DisplayStatus[] = ["ready", "needs_input", "draft", "approved", "stale", "locked"];

/** The loop every step follows, in three short lines. Shown in the How it works dialog only. */
export function Loop() {
  return (
    <ol className="how-steps">
      <li>
        <strong>Tell the agent what you want.</strong> Answer its questions, attach documents.
      </li>
      <li>
        <strong>Check the result</strong> on the right. Edit it or ask for changes.
      </li>
      <li>
        <strong>Approve it.</strong> The next step unlocks.
      </li>
    </ol>
  );
}

// Opened from the sidebar when asked for: the loop and what the word next to each step means. Nothing here is needed to use the tool.
export function HowItWorks({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = dialog.current;
    if (d && !d.open) d.showModal?.();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="how-it-works"
      aria-labelledby="how-heading"
      onClose={onClose}
      onClick={(e) => e.target === dialog.current && onClose()} // a click on the backdrop closes it
    >
      <header>
        <h2 id="how-heading">How it works</h2>
        <button type="button" className="icon-button icon-button-sm" aria-label="Close" onClick={onClose}>
          <Icon name="close" size={14} />
        </button>
      </header>
      <Loop />
      <p className="how-note">Change an earlier step and the steps after it say Update. Press Update to redo them. Do not approve them as they are.</p>
      <dl className="legend">
        {ORDER.map((s) => (
          <div key={s} data-status={s}>
            <dt>
              <span className="legend-node" aria-hidden="true" />
              {ACTION_LABEL[s]}
            </dt>
            <dd>{ACTION_MEANING[s]}</dd>
          </div>
        ))}
      </dl>
    </dialog>
  );
}
