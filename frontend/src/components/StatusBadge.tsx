import { ACTION_LABEL, DISPLAY_LABEL, type DisplayStatus } from "../lib/status";

// The same word as under the step in the pipeline, so there is one vocabulary.
// `label` replaces the word where a phase has its own (Maintenance: "Change 2 of 6", "Ready").
export function StatusBadge({ status, label, title }: { status: DisplayStatus; label?: string; title?: string }) {
  return (
    <span className="badge" data-status={status} title={title ?? DISPLAY_LABEL[status]}>
      <span className="badge-dot" aria-hidden="true" />
      {label ?? ACTION_LABEL[status]}
    </span>
  );
}
