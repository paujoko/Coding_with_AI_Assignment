import { useEffect, useRef, useState } from "react";
import type { Project } from "../api/types";
import { ACTION_LABEL, displayStatus, focusPhase } from "../lib/status";
import { Icon } from "./Icon";
import { Mark } from "./Mark";

interface Props {
  projects: Project[];
  current: Project | null;
  creating: boolean;
  busy: boolean;
  onPick: (id: string) => void;
  onNew: () => void;
}

const where = (p: Project) => {
  const next = focusPhase(p.phases);
  return `${next.title}: ${ACTION_LABEL[displayStatus(next)].toLowerCase()}`;
};

// Project picker at the top of the sidebar, as in Linear or Vercel: the current project, a menu with the others.
export function ProjectSwitcher({ projects, current, creating, busy, onPick, onNew }: Props) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", close);
    };
  }, [open]);

  const shown = creating ? null : current;
  return (
    <div className="switcher" ref={box}>
      <button
        type="button"
        className="switcher-button"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={busy}
        onClick={() => setOpen(!open)}
      >
        {shown ? <Mark size={20} phases={shown.phases} /> : <Icon name="plus" />}
        <span className="switcher-text">
          <span className="switcher-name">{shown ? shown.name : "New project"}</span>
          {shown && <span className="switcher-state">{where(shown)}</span>}
        </span>
        <Icon name="chevron" size={12} className="switcher-chevron" />
      </button>
      {open && (
        <div className="switcher-menu" role="menu" aria-label="Projects">
          {projects.map((p) => (
            <button
              key={p.id}
              type="button"
              role="menuitem"
              className="switcher-item"
              aria-current={p.id === shown?.id || undefined}
              onClick={() => {
                setOpen(false);
                onPick(p.id);
              }}
            >
              <Mark size={18} phases={p.phases} />
              <span className="switcher-text">
                <span className="switcher-name">{p.name}</span>
                <span className="switcher-state">{where(p)}</span>
              </span>
              {p.id === shown?.id && <Icon name="check" size={14} />}
            </button>
          ))}
          <button
            type="button"
            role="menuitem"
            className="switcher-item switcher-new"
            onClick={() => {
              setOpen(false);
              onNew();
            }}
          >
            <Icon name="plus" />
            New project
          </button>
        </div>
      )}
    </div>
  );
}
