import type { PhaseState } from "../api/types";
import { ACTION_LABEL, DISPLAY_LABEL, displayStatus, needsDeveloper, wingOf } from "../lib/status";
import { Icon } from "./Icon";

interface Props {
  phases: PhaseState[];
  selected: string | null;
  onSelect: (id: string) => void;
  disabled?: boolean; // while an agent works, so the result lands in the phase that asked for it
}

// Plain words first; the course's wing names stay as a quiet second label.
const GROUPS = [
  { wing: "left", label: "Specify", note: "left wing" },
  { wing: "body", label: "Build", note: "body" },
  { wing: "right", label: "Verify and run", note: "right wing" },
] as const;

// The pipeline as numbered steps on a line. Under each step one word says what to do there
// (Start, Answer, Review, Done, Update, Locked, Soon). The track turns solid once a step is
// approved and breaks where a later step went out of date.
export function Pipeline({ phases, selected, onSelect, disabled = false }: Props) {
  return (
    <nav className="pipeline" aria-label="Steps">
      <ol className="pipeline-groups" aria-hidden="true">
        {GROUPS.map((g) => (
          <li key={g.wing} data-wing={g.wing}>
            <span className="group-label">{g.label}</span> <span className="group-note">{g.note}</span>
          </li>
        ))}
      </ol>
      <ol className="pipeline-stations">
        {phases.map((phase, i) => {
          const status = displayStatus(phase);
          const next = phases[i + 1];
          const track = !next ? undefined : next.status === "stale" ? "broken" : phase.status === "approved" ? "done" : "open";
          return (
            <li key={phase.id} data-wing={wingOf(i)} data-track={track}>
              <button
                type="button"
                className="station"
                data-status={status}
                data-attention={needsDeveloper(status) || status === "ready" || undefined}
                aria-current={selected === phase.id ? "step" : undefined}
                disabled={disabled}
                title={`Step ${i + 1}: ${phase.title}, ${DISPLAY_LABEL[status].toLowerCase()}`}
                onClick={() => onSelect(phase.id)}
              >
                <span className="station-node" aria-hidden="true">
                  {status === "approved" ? <Icon name="check" size={12} /> : i + 1}
                </span>
                <span className="station-title">{phase.title}</span>
                <span className="station-status">
                  {ACTION_LABEL[status]}
                  <span className="sr-only">, {DISPLAY_LABEL[status]}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
