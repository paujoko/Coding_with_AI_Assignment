import { ACTION_LABEL, DISPLAY_LABEL, type DisplayStatus } from "../lib/status";

// The same word as under the step in the pipeline, so there is one vocabulary.
export function StatusBadge({ status }: { status: DisplayStatus }) {
  return (
    <span className="badge" data-status={status} title={DISPLAY_LABEL[status]}>
      <span className="badge-dot" aria-hidden="true" />
      {ACTION_LABEL[status]}
    </span>
  );
}
