import type { ActivityEvent, PhaseState } from "../api/types";
import { eventLabel } from "../lib/status";

interface Props {
  events: ActivityEvent[];
  phases: PhaseState[];
}

const stamp = (iso: string) =>
  new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });

// The full project log: what the system did, newest first.
export function ActivityView({ events, phases }: Props) {
  const title = (id: string | null) => (id ? phases.find((p) => p.id === id)?.title ?? id : "Project");
  const recent = [...events].reverse();
  return (
    <section className="page" aria-labelledby="activity-heading">
      <header className="page-head">
        <h1 id="activity-heading">Activity</h1>
        <p className="lede">Every step the orchestrator and the agents took in this project, newest first. Model calls show provider, attempts and time.</p>
      </header>
      {recent.length === 0 ? (
        <p className="empty-note">Nothing happened yet.</p>
      ) : (
        <table className="log">
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Phase</th>
              <th scope="col">Step</th>
              <th scope="col">Details</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((e) => (
              <tr key={e.seq} data-kind={e.kind}>
                <td className="log-time">
                  <time dateTime={e.at}>{stamp(e.at)}</time>
                </td>
                <td>{title(e.phase)}</td>
                <td>
                  <span className="log-kind" data-kind={e.kind}>
                    {eventLabel(e.kind)}
                  </span>
                </td>
                <td>{e.summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
