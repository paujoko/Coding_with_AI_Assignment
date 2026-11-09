import type { Health, PhaseState, Project } from "../api/types";
import { DISPLAY_LABEL, displayStatus } from "../lib/status";
import { Icon } from "./Icon";
import { Mark } from "./Mark";

interface Props {
  projects: Project[];
  current: string | null;
  creating: boolean;
  busy: boolean; // switching projects mid-request would show the result in the wrong project
  health: Health | null;
  onPick: (id: string) => void;
  onNew: () => void;
}

// The phase a project waits on: the first implemented one that is not approved yet.
export function focusPhase(phases: PhaseState[]): PhaseState {
  return phases.find((p) => p.implemented && p.can_run && p.status !== "approved") ?? phases[0];
}

export function Sidebar({ projects, current, creating, busy, health, onPick, onNew }: Props) {
  return (
    <aside className="sidebar">
      <p className="brand">
        <Mark size={24} />
        <span>Wings</span>
      </p>

      <button type="button" className="button sidebar-new" aria-pressed={creating} onClick={onNew} disabled={busy}>
        <Icon name="plus" size={14} />
        New project
      </button>

      {projects.length > 0 && (
        <nav className="projects" aria-label="Projects">
          <h2>Projects</h2>
          <ul>
            {projects.map((p) => {
              const next = focusPhase(p.phases);
              return (
                <li key={p.id}>
                  <button type="button" aria-current={p.id === current && !creating ? "page" : undefined} disabled={busy} onClick={() => onPick(p.id)}>
                    <Mark size={18} phases={p.phases} />
                    <span className="project-name">{p.name}</span>
                    <span className="project-state">
                      {next.title}, {DISPLAY_LABEL[displayStatus(next)].toLowerCase()}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      )}

      {/* Phone layout: the list above becomes this picker. */}
      {projects.length > 0 && (
        <label className="project-select">
          <span className="sr-only">Project</span>
          <select value={creating ? "" : current ?? ""} disabled={busy} onChange={(e) => e.target.value && onPick(e.target.value)}>
            {creating && <option value="">New project</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {health && (
        <footer className="runtime">
          <p title={health.llm_provider === "mock" ? "Scripted replies, no API key, no cost" : undefined}>
            <span className="runtime-dot" data-mock={health.llm_provider === "mock" || undefined} aria-hidden="true" />
            {health.llm_provider === "mock" ? "Mock model" : `Models via ${health.llm_provider}`}
            <a href="http://localhost:8810/docs" target="_blank" rel="noreferrer">
              API <Icon name="external" size={12} />
            </a>
          </p>
          {!health.renderer && <p>Diagrams shown as source (no PlantUML)</p>}
        </footer>
      )}
    </aside>
  );
}
