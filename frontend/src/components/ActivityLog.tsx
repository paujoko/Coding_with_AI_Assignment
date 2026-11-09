import type { ActivityEvent } from "../api/types";

const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function ActivityLog({ events }: { events: ActivityEvent[] }) {
  const recent = events.slice(-40).reverse();
  return (
    <section className="activity" aria-label="Activity log">
      <h2>What the system did</h2>
      {recent.length === 0 ? (
        <p className="empty">Nothing yet.</p>
      ) : (
        <ol>
          {recent.map((e) => (
            <li key={e.seq} data-kind={e.kind}>
              <time dateTime={e.at}>{time(e.at)}</time>
              <span className="event-kind">{e.kind}</span>
              <span className="event-summary">{e.summary}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
