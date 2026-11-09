import type { PhaseState } from "../api/types";
import { MARK_STROKES } from "../lib/mark";
import { displayStatus } from "../lib/status";

interface Props {
  size?: number;
  phases?: PhaseState[]; // when given, each stroke shows the status of its phase
  title?: string;
}

// The Wings mark. Static it is the logo; with phases it doubles as a project's progress.
export function Mark({ size = 24, phases, title }: Props) {
  const width = size <= 18 ? 3.2 : size <= 32 ? 2.9 : 2.6;
  return (
    <svg
      className="mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      strokeLinecap="round"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {MARK_STROKES.map(([x1, y1, x2, y2], i) => (
        <line
          key={i}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          strokeWidth={width}
          data-status={phases?.[i] ? displayStatus(phases[i]) : undefined}
        />
      ))}
    </svg>
  );
}
