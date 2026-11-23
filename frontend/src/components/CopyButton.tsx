import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

interface Props {
  text: string; // what lands on the clipboard
  label?: string; // the button's words; "Copy" when omitted
  describe?: string; // what is copied, for screen readers and the tooltip ("Copy the start command")
  className?: string;
}

// A copy button that says "Copied" in words (same clipboard pattern as the chat replies and the file viewer,
// but with a visible confirmation: on a projector an icon that changes for a second is easy to miss).
export function CopyButton({ text, label = "Copy", describe, className = "button button-quiet copy-button" }: Props) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<number>();
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const settle = (next: "copied" | "failed") => {
    setState(next);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setState("idle"), 1800);
  };
  const copy = () => {
    const done = navigator.clipboard?.writeText(text);
    if (!done) return settle("failed"); // no clipboard here (an insecure page): say so instead of pretending
    done.then(
      () => settle("copied"),
      () => settle("failed"),
    );
  };

  return (
    <button type="button" className={className} data-state={state} title={describe ?? label} aria-label={state === "idle" ? describe : undefined} onClick={copy}>
      <Icon name={state === "copied" ? "check" : "copy"} size={14} />
      <span aria-live="polite">{state === "copied" ? "Copied" : state === "failed" ? "Not copied" : label}</span>
    </button>
  );
}
