import type { PhaseState } from "../api/types";
import { buildSteps, type Mark, MARK_WORD, stepMark, stepTitle } from "../lib/flow";
import { Icon } from "./Icon";

interface Props {
  phases: PhaseState[];
  redo: string[];
  running: string | null; // the step an agent works on
  selected: string | null;
  onSelect: (id: string) => void;
  disabled?: boolean; // while an agent works, so the result lands in the step that asked for it
}

function MarkIcon({ mark }: { mark: Mark }) {
  if (mark === "accepted") return <Icon name="check" size={12} />;
  if (mark === "redo") return <Icon name="refresh" size={12} />;
  if (mark === "working") return <Icon name="spinner" size={12} className="spin" />;
  return null; // the dot for "yours" and the empty ring for "later" are drawn by CSS
}

// The build as a checklist with a line through it: accepted steps are ticked, the step that waits for you has a
// filled dot, steps that have to follow a change show the redo arrow. Your program sits below the line.
export function StepRail({ phases, redo, running, selected, onSelect, disabled = false }: Props) {
  const steps = buildSteps(phases);
  const program = phases.find((p) => p.id === "maintenance" && p.implemented);
  const done = steps.every((p) => p.status === "approved") && redo.length === 0;
  return (
    <nav className="rail" aria-label="Steps">
      <ol className="rail-steps">
        {steps.map((p) => {
          const mark = stepMark(p, running, redo);
          const word = mark === "yours" || mark === "redo" || mark === "working" ? MARK_WORD[mark] : null;
          return (
            <li key={p.id} data-mark={mark}>
              <button
                type="button"
                className="rail-step"
                data-mark={mark}
                aria-current={selected === p.id ? "step" : undefined}
                disabled={disabled}
                onClick={() => onSelect(p.id)}
              >
                <span className="rail-dot" aria-hidden="true">
                  <MarkIcon mark={mark} />
                </span>
                <span className="rail-title">{stepTitle(p)}</span>
                {word ? <span className="rail-word">{word}</span> : <span className="sr-only">{MARK_WORD[mark]}</span>}
              </button>
            </li>
          );
        })}
      </ol>
      {program && (
        <button
          type="button"
          className="rail-program"
          data-ready={done || undefined}
          aria-current={selected === program.id ? "step" : undefined}
          disabled={disabled}
          onClick={() => onSelect(program.id)}
        >
          <span className="rail-program-dot" aria-hidden="true" />
          <span className="rail-title">Your program</span>
          {done && <span className="rail-word">Ready</span>}
        </button>
      )}
    </nav>
  );
}
