import type { Health, Project } from "../api/types";
import { Icon } from "./Icon";
import { Mark } from "./Mark";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { StepList } from "./StepList";

export type View = "phase" | "trace" | "activity";

interface Props {
  projects: Project[];
  project: Project | null;
  creating: boolean;
  busy: boolean; // switching projects or steps mid-request would show the result in the wrong place
  health: Health | null;
  view: View;
  phaseId: string | null;
  helpOpen: boolean;
  settingsOpen: boolean;
  onPick: (id: string) => void;
  onNew: () => void;
  onPhase: (id: string) => void;
  onView: (view: View) => void;
  onHelp: () => void;
  onSettings: () => void;
}

// Everything you navigate lives here, as in GitHub's run page or Linear: project, its steps, its views.
// The main area belongs to the step you work on.
export function Sidebar(p: Props) {
  const inProject = p.project && !p.creating && !p.settingsOpen;
  return (
    <aside className="sidebar">
      <p className="brand">
        <Mark size={22} />
        <span>Wings</span>
      </p>

      <ProjectSwitcher projects={p.projects} current={p.project} creating={p.creating} busy={p.busy} onPick={p.onPick} onNew={p.onNew} />

      {p.project && !p.creating && (
        <>
          <nav className="side-steps" aria-label="Steps">
            <StepList phases={p.project.phases} selected={inProject && p.view === "phase" ? p.phaseId : null} onSelect={p.onPhase} disabled={p.busy} />
          </nav>
          <nav className="side-nav" aria-label="Project">
            <button type="button" aria-current={inProject && p.view === "trace" ? "page" : undefined} disabled={p.busy} onClick={() => p.onView("trace")}>
              <Icon name="matrix" size={14} />
              Traceability
            </button>
            <button type="button" aria-current={inProject && p.view === "activity" ? "page" : undefined} disabled={p.busy} onClick={() => p.onView("activity")}>
              <Icon name="sparkle" size={14} />
              Activity
            </button>
            <button type="button" aria-pressed={p.helpOpen} onClick={p.onHelp}>
              <Icon name="help" size={14} />
              How it works
            </button>
          </nav>
        </>
      )}

      {p.health && (
        <footer className="runtime">
          <button
            type="button"
            className="runtime-model"
            aria-pressed={p.settingsOpen}
            disabled={p.busy || !p.health.settings}
            onClick={p.onSettings}
            title="Choose the AI model and paste an API key"
          >
            <span
              className="runtime-dot"
              data-mock={p.health.llm_provider === "mock" || undefined}
              data-missing={p.health.llm_ready === false || undefined}
              aria-hidden="true"
            />
            <span className="runtime-label">
              {p.health.llm_provider === "mock" ? "Demo model" : p.health.llm_provider === "openai" ? "OpenAI" : "OpenRouter"}
              {p.health.llm_ready === false && <span className="runtime-warn"> · key missing</span>}
            </span>
            <Icon name="settings" size={14} />
          </button>
          {!p.health.renderer && <p>Diagrams shown as source (no PlantUML)</p>}
        </footer>
      )}
    </aside>
  );
}
