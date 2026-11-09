import type { PhaseState } from "../api/types";
import { DISPLAY_LABEL, displayStatus, needsDeveloper, wingOf } from "../lib/status";

interface Props {
  phases: PhaseState[];
  selected: string | null;
  onSelect: (id: string) => void;
  disabled?: boolean; // while an agent works, so the result lands in the phase that asked for it
}

const GROUPS = [
  { wing: "left", label: "Left wing" },
  { wing: "body", label: "Body" },
  { wing: "right", label: "Right wing" },
] as const;

// The pipeline drawn as a line with seven stations. The track between two stations shows
// whether work flows through: solid once the earlier phase is approved, broken where a
// later phase went out of date. Code generation, the body, is the one square station.
export function Pipeline({ phases, selected, onSelect, disabled = false }: Props) {
  return (
    <nav className="pipeline" aria-label="Pipeline">
      <ol className="pipeline-groups" aria-hidden="true">
        {GROUPS.map((g) => (
          <li key={g.wing} data-wing={g.wing}>
            {g.label}
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
                aria-current={selected === phase.id ? "step" : undefined}
                disabled={disabled}
                onClick={() => onSelect(phase.id)}
              >
                <span className="station-node" aria-hidden="true" />
                <span className="station-number">P{i + 1}</span>
                <span className="station-title">{phase.title}</span>
                {/* Visible only where the developer has to act; the node colour carries the rest. */}
                <span className={needsDeveloper(status) ? "station-status" : "sr-only"}>{DISPLAY_LABEL[status]}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
