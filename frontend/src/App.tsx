import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api/client";
import type { ActivityEvent, Artifact, Coverage, Health, Message, PhaseInfo, Project } from "./api/types";
import { ActivityLog } from "./components/ActivityLog";
import { PhaseWorkspace } from "./components/PhaseWorkspace";
import { ProjectBar } from "./components/ProjectBar";
import { Wingspan } from "./components/Wingspan";

const LAST_PROJECT = "wings.project";

function remember(id: string) {
  try {
    localStorage.setItem(LAST_PROJECT, id);
  } catch {
    /* storage can be unavailable; the app works without it */
  }
}

function recall(): string | null {
  try {
    return localStorage.getItem(LAST_PROJECT);
  } catch {
    return null;
  }
}

// The phase to show when a project opens: the first implemented one that still needs the developer.
function focusPhase(project: Project): string {
  const open = project.phases.find((p) => p.implemented && p.can_run && p.status !== "approved");
  return (open ?? project.phases[0]).id;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<PhaseInfo[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [phaseId, setPhaseId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : String(e));

  useEffect(() => {
    Promise.all([api.health(), api.phases(), api.projects()])
      .then(([h, c, ps]) => {
        setHealth(h);
        setCatalog(c);
        setProjects(ps);
        const start = ps.find((p) => p.id === recall()) ?? ps[ps.length - 1];
        if (start) open(start);
      })
      .catch(fail);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const open = (p: Project) => {
    setProject(p);
    setPhaseId(focusPhase(p));
    setEvents([]);
    remember(p.id);
  };

  const loadPhase = useCallback(async (pid: string, phase: string) => {
    const [m, a, c] = await Promise.all([api.messages(pid, phase), api.artifacts(pid, phase), api.trace(pid)]);
    setMessages(m);
    setArtifacts(a);
    setCoverage(c);
  }, []);

  useEffect(() => {
    if (project && phaseId) loadPhase(project.id, phaseId).catch(fail);
  }, [project?.id, phaseId, loadPhase]); // eslint-disable-line react-hooks/exhaustive-deps

  // Activity log: poll faster while an agent is working.
  useEffect(() => {
    if (!project) return;
    let stop = false;
    const tick = async () => {
      const after = events.length ? events[events.length - 1].seq : 0;
      const fresh = await api.events(project.id, after).catch(() => []);
      if (!stop && fresh.length) setEvents((ev) => [...ev, ...fresh.filter((f) => f.seq > (ev.at(-1)?.seq ?? 0))]);
    };
    const id = window.setInterval(tick, busy ? 700 : 3000);
    tick();
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [project?.id, busy, events.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async (p: Project) => {
    setProject(p);
    setProjects((ps) => ps.map((x) => (x.id === p.id ? p : x)));
    if (phaseId) await loadPhase(p.id, phaseId);
  };

  // Returns whether the work succeeded. rethrow: editors keep the developer's unsaved text when a save fails.
  // Navigation is disabled while busy, so project and phase cannot change under a running request.
  const guarded = async (work: () => Promise<void>, rethrow = false): Promise<boolean> => {
    setBusy(true);
    setError(null);
    try {
      await work();
      return true;
    } catch (e) {
      fail(e);
      if (project && phaseId) await loadPhase(project.id, phaseId).catch(() => undefined);
      if (rethrow) throw e;
      return false;
    } finally {
      setBusy(false);
    }
  };

  if (!health && error) {
    return (
      <main className="boot-error">
        <h1>Wings cannot reach its backend</h1>
        <p>{error}</p>
        <p>Start it with the preview tool (wings-backend) or run: wings serve</p>
      </main>
    );
  }

  const index = project && phaseId ? project.phases.findIndex((p) => p.id === phaseId) : -1;
  const info = catalog.find((c) => c.id === phaseId);

  return (
    <div className="app">
      <ProjectBar
        projects={projects}
        current={project?.id ?? null}
        health={health}
        busy={busy}
        onPick={(id) => {
          const p = projects.find((x) => x.id === id);
          if (p) open(p);
        }}
        onCreate={(name) =>
          guarded(async () => {
            const p = await api.createProject(name);
            setProjects((ps) => [...ps, p]);
            open(p);
          })
        }
      />
      {error && (
        <div className="error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}
      {!project ? (
        <main className="welcome">
          <h1>Start with a description of the software you want</h1>
          <p>
            Create a project above. Wings walks it from requirements through design, code, tests and deployment to
            maintenance, and stops after every phase so you can review, change and approve what the agents produced.
          </p>
        </main>
      ) : (
        <main>
          <Wingspan phases={project.phases} selected={phaseId} onSelect={setPhaseId} disabled={busy} />
          {info && index >= 0 && (
            <PhaseWorkspace
              key={`${project.id}-${phaseId}`}
              projectId={project.id}
              index={index}
              info={info}
              state={project.phases[index]}
              all={project.phases}
              messages={messages}
              artifacts={artifacts}
              coverage={coverage}
              canRender={health?.renderer ?? false}
              busy={busy}
              onRun={(action, input) =>
                guarded(async () => {
                  const r = await api.run(project.id, info.id, action, input);
                  await refresh(r.project);
                })
              }
              onApprove={() => guarded(async () => refresh(await api.approve(project.id, info.id)))}
              onReopen={() => guarded(async () => refresh(await api.reopen(project.id, info.id)))}
              onSaveContent={async (aid, content) => {
                await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { content })).project), true);
              }}
              onSaveText={async (aid, text) => {
                await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { text })).project), true);
              }}
            />
          )}
          <ActivityLog events={events} />
        </main>
      )}
    </div>
  );
}
