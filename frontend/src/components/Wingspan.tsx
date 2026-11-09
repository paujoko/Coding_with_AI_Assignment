import type { PhaseState } from "../api/types";
import { STATUS_LABEL, wingOf } from "../lib/status";

interface Props {
  phases: PhaseState[];
  selected: string | null;
  onSelect: (id: string) => void;
  disabled?: boolean; // while an agent works, so the result lands in the phase that asked for it
}

// The pipeline drawn as a bird: requirements to refinement are the left wing,
// code generation is the body, testing to maintenance the right wing.
export function Wingspan({ phases, selected, onSelect, disabled = false }: Props) {
  const groups = { left: [] as JSX.Element[], body: [] as JSX.Element[], right: [] as JSX.Element[] };
  phases.forEach((phase, index) => {
    groups[wingOf(index)].push(
      <button
        key={phase.id}
        type="button"
        className="phase"
        data-status={phase.status}
        data-planned={!phase.implemented || undefined}
        aria-current={selected === phase.id ? "step" : undefined}
        disabled={disabled}
        onClick={() => onSelect(phase.id)}
      >
        <span className="phase-number">P{index + 1}</span>
        <span className="phase-title">{phase.title}</span>
        <span className="phase-status">
          <span className="dot" aria-hidden="true" />
          {phase.implemented ? STATUS_LABEL[phase.status] : "Planned"}
        </span>
      </button>,
    );
  });
  return (
    <nav className="wingspan" aria-label="Pipeline">
      <div className="wing wing-left">{groups.left}</div>
      <div className="wing-body">{groups.body}</div>
      <div className="wing wing-right">{groups.right}</div>
    </nav>
  );
}
