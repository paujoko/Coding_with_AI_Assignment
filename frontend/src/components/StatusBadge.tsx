import { BADGE_LABEL, DISPLAY_LABEL, type DisplayStatus } from "../lib/status";

// The status of a step in words: To do, Your answer needed, Ready for review, Done, Out of date.
export function StatusBadge({ status, label, title }: { status: DisplayStatus; label?: string; title?: string }) {
  return (
    <span className="badge" data-status={status} title={title ?? DISPLAY_LABEL[status]}>
      <span className="badge-dot" aria-hidden="true" />
      {label ?? BADGE_LABEL[status]}
    </span>
  );
}
