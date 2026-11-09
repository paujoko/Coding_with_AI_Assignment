import { DISPLAY_LABEL, type DisplayStatus } from "../lib/status";

export function StatusBadge({ status }: { status: DisplayStatus }) {
  return (
    <span className="badge" data-status={status}>
      <span className="badge-dot" aria-hidden="true" />
      {DISPLAY_LABEL[status]}
    </span>
  );
}
