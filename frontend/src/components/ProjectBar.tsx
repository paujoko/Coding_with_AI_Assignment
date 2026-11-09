import { useState } from "react";
import type { Health, Project } from "../api/types";

interface Props {
  projects: Project[];
  current: string | null;
  health: Health | null;
  onPick: (id: string) => void;
  onCreate: (name: string) => void;
}

export function ProjectBar({ projects, current, health, onPick, onCreate }: Props) {
  const [name, setName] = useState("");
  return (
    <header className="topbar">
      <p className="brand">Wings</p>
      <div className="project-picker">
        {projects.length > 0 && (
          <label>
            <span className="sr-only">Project</span>
            <select value={current ?? ""} onChange={(e) => onPick(e.target.value)}>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) onCreate(name.trim());
            setName("");
          }}
        >
          <input aria-label="New project name" placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={!name.trim()}>
            Create project
          </button>
        </form>
      </div>
      {health && (
        <p className="runtime" title={health.workspace_dir}>
          Models: {health.llm_provider === "mock" ? "scripted mock, no API calls" : health.llm_provider}
          {!health.renderer && ", diagrams shown as source"}
        </p>
      )}
    </header>
  );
}
