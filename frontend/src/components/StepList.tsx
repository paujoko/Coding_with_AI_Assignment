import type { OpenChange, PhaseState } from "../api/types";
import { changeLine, maintenanceWord } from "../lib/changes";
import { ACTION_LABEL, DISPLAY_LABEL, displayStatus, type DisplayStatus, wingOf } from "../lib/status";
import { Icon } from "./Icon";

interface Props {
  phases: PhaseState[];
  selected: string | null;
  onSelect: (id: string) => void;
  disabled?: boolean; // while an agent works, so the result lands in the phase that asked for it
  openChange?: OpenChange | null; // the change being carried through: Maintenance says where it stands
}

// Plain words first; the course's wing names stay as a quiet second label.
const GROUPS = [
  { wing: "left", label: "Specify", note: "left wing" },
  { wing: "body", label: "Build", note: "body" },
  { wing: "right", label: "Verify and run", note: "right wing" },
] as const;

/** Steps where the developer has to do something show their word ("Review"); the others only an icon. */
const YOUR_TURN: DisplayStatus[] = ["ready", "needs_input", "draft", "stale"];

function StepIcon({ status }: { status: DisplayStatus }) {
  if (status === "approved") return <Icon name="check" size={12} />;
  if (status === "locked") return <Icon name="lock" size={12} />;
  if (status === "stale") return <Icon name="alert" size={12} />;
  return null; // rings and dots are drawn by CSS
}

// The phases as a checklist, like the job list of a CI run or a coding agent's plan:
// done steps are ticked, the steps that wait for you say what to do, unbuilt ones stay quiet.
export function StepList({ phases, selected, onSelect, disabled = false, openChange = null }: Props) {
  return (
    <ol className="step-groups">
      {GROUPS.map((g) => {
        const steps = phases.map((p, i) => ({ p, i })).filter(({ i }) => wingOf(i) === g.wing);
        return (
          <li key={g.wing} className="step-group" data-wing={g.wing}>
            <p className="step-group-label" aria-hidden="true">
              {g.label} <span>{g.note}</span>
            </p>
            <ol className="steps" aria-label={g.label}>
              {steps.map(({ p, i }) => {
                const real = displayStatus(p);
                // Maintenance is not a step to finish: it carries changes. Its word is the open change, or nothing.
                const maintenance = p.id === "maintenance" && real !== "planned" && real !== "locked";
                const own = maintenance ? maintenanceWord(real, openChange) : undefined;
                const tracking = maintenance && openChange ? openChange : null;
                // A result in Maintenance (a check, a change) is nothing to approve: it reads as ready.
                const status = maintenance && !tracking && real === "draft" ? "ready" : real;
                const turn = own === undefined ? YOUR_TURN.includes(status) : own !== null;
                const word = own === undefined ? ACTION_LABEL[status] : (own ?? "Ready");
                return (
                  <li key={p.id} data-status={status} data-done={p.status === "approved" || undefined}>
                    <button
                      type="button"
                      className="step"
                      data-status={status}
                      data-change={tracking ? "" : undefined}
                      aria-current={selected === p.id ? "step" : undefined}
                      disabled={disabled}
                      title={`Step ${i + 1}: ${p.title}, ${tracking ? changeLine(tracking, phases) : own === null ? "ready" : DISPLAY_LABEL[status].toLowerCase()}`}
                      onClick={() => onSelect(p.id)}
                    >
                      <span className="step-icon" aria-hidden="true">
                        <StepIcon status={status} />
                      </span>
                      <span className="step-title">{p.title}</span>
                      {turn || status === "planned" ? (
                        <span className="step-word">{word}</span>
                      ) : (
                        <span className="sr-only">{word}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ol>
          </li>
        );
      })}
    </ol>
  );
}
