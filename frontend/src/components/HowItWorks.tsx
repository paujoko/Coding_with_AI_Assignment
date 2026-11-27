import { useEffect, useRef } from "react";
import { Icon } from "./Icon";

/** The whole model in one sentence: shown on the start page and in How it works (docs/code/design.md). */
export const MODEL =
  "Your program is built in six steps. At each step you see what was made: you accept it, or you say what to change. When you change something later steps depend on, those steps are redone with you, one by one.";

// What the marks in the step list mean. One line each.
const MARKS = [
  { mark: "accepted", word: "Accepted", meaning: "You accepted it. Later steps build on it." },
  { mark: "yours", word: "Your turn", meaning: "A result or a question waits for you." },
  { mark: "redo", word: "Redo", meaning: "Something it builds on changed. It is made again with you." },
  { mark: "later", word: "Later", meaning: "Comes after the steps above." },
];

// Opened from the sidebar when asked for. Nothing here is needed to use the tool.
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
        <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
          <Icon name="close" size={14} />
        </button>
      </header>
      <p className="how-model">{MODEL}</p>
      <p className="how-note">
        A yellow sentence is the one thing to read on a screen. <em>Checked by code</em> means no model judged it.
      </p>
      <ul className="how-marks">
        {MARKS.map((m) => (
          <li key={m.mark}>
            <span className="rail-step" data-mark={m.mark} aria-hidden="true">
              <span className="rail-dot">{m.mark === "accepted" ? <Icon name="check" size={12} /> : m.mark === "redo" ? <Icon name="refresh" size={12} /> : null}</span>
            </span>
            <strong>{m.word}</strong>
            <span>{m.meaning}</span>
          </li>
        ))}
      </ul>
    </dialog>
  );
}
