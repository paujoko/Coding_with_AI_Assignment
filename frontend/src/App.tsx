import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api/client";
import type { ActivityEvent, Artifact, Health, Message, PhaseInfo, Project, Trace } from "./api/types";
import { ActivityView } from "./components/ActivityView";
import { Icon } from "./components/Icon";
import { NewProject } from "./components/NewProject";
import type { Values } from "./components/Composer";
import { type Focus, PhaseWorkspace } from "./components/PhaseWorkspace";
import { Pipeline } from "./components/Pipeline";
import { focusPhase, Sidebar } from "./components/Sidebar";
import { TraceView } from "./components/TraceView";

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

type View = "phase" | "trace" | "activity";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<PhaseInfo[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [project, setProject] = useState<Project | null>(null);
  const [creating, setCreating] = useState(false);
  const [view, setView] = useState<View>("phase");
  const [phaseId, setPhaseId] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<{ project: string; values: Values } | null>(null);

  // What the screen shows right now. Responses that arrive for another project or phase are dropped,
  // so a slow request can never paint its data into the phase the developer moved to.
  const shown = useRef<{ project: string | null; phase: string | null }>({ project: null, phase: null });
  shown.current = { project: project?.id ?? null, phase: phaseId };

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : String(e));

  const open = (p: Project, phase?: string) => {
    if (p.id !== project?.id) setEvents([]);
    setProject(p);
    setCreating(false);
    setView("phase");
    setPhaseId(phase ?? focusPhase(p.phases).id);
    setFocus({});
    remember(p.id);
  };

  useEffect(() => {
    Promise.all([api.health(), api.phases(), api.projects()])
      .then(([h, c, ps]) => {
        setHealth(h);
        setCatalog(c);
        setProjects(ps);
        const start = ps.find((p) => p.id === recall()) ?? ps[ps.length - 1];
        if (start) open(start);
        else setCreating(true);
      })
      .catch(fail)
      .finally(() => setLoaded(true));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadPhase = useCallback(async (pid: string, phase: string) => {
    const [m, a, t] = await Promise.all([api.messages(pid, phase), api.artifacts(pid, phase), api.trace(pid)]);
    if (shown.current.project !== pid || shown.current.phase !== phase) return;
    setMessages(m);
    setArtifacts(a);
    setTrace(t);
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
    const id = window.setInterval(tick, busy ? 600 : 3000);
    tick();
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [project?.id, busy, events.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async (p: Project) => {
    setProject(p);
    setProjects((ps) => ps.map((x) => (x.id === p.id ? p : x)));
    if (shown.current.phase) await loadPhase(p.id, shown.current.phase);
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
      const { project: pid, phase } = shown.current;
      if (pid && phase) await loadPhase(pid, phase).catch(() => undefined);
      if (rethrow) throw e;
      return false;
    } finally {
      setBusy(false);
    }
  };

  const create = (name: string, description: string) =>
    guarded(async () => {
      const p = await api.createProject(name);
      setProjects((ps) => [...ps, p]);
      open(p, "requirements");
      if (description) {
        // The developer already said what they want: hand it to the analyst right away.
        // If that fails, the description waits in the composer of the new project.
        setPrefill({ project: p.id, values: { "start.description": description } });
        const r = await api.run(p.id, "requirements", "start", { description });
        setPrefill(null);
        setProject(r.project);
        setProjects((ps) => ps.map((x) => (x.id === p.id ? r.project : x)));
        await loadPhase(p.id, "requirements");
      }
    });

  // Navigation waits while an agent works, so its result lands in the phase that asked for it.
  const goToPhase = (phase: string, f: Focus = {}) => {
    if (busy) return;
    setView("phase");
    setPhaseId(phase);
    setFocus(f);
  };
  const openRequirement = (id: string) => goToPhase("requirements", { requirement: id });
  const openArtifact = (artifactId: string, phase?: string) => {
    const owner = phase ?? artifacts.find((a) => a.id === artifactId)?.phase ?? trace?.artifacts.find((a) => a.id === artifactId)?.phase;
    if (owner) goToPhase(owner, { artifact: artifactId });
  };

  if (loaded && !health && error) {
    return (
      <main className="boot-error">
        <h1>Wings cannot reach its backend</h1>
        <p>{error}</p>
        <p>
          Start it from <code>backend/</code> with <code>python -m uvicorn wings.main:app --port 8810</code>, then reload this page.
        </p>
      </main>
    );
  }

  const index = project && phaseId ? project.phases.findIndex((p) => p.id === phaseId) : -1;
  const info = catalog.find((c) => c.id === phaseId);

  return (
    <div className="app">
      <Sidebar
        projects={projects}
        current={project?.id ?? null}
        creating={creating}
        busy={busy}
        health={health}
        onPick={(id) => {
          const p = projects.find((x) => x.id === id);
          if (p) open(p);
        }}
        onNew={() => setCreating(true)}
      />
      <main className="main">
        {error && (
          <div className="alert" role="alert">
            <Icon name="alert" />
            <p>{error}</p>
            <button type="button" className="button button-quiet" onClick={() => setError(null)} aria-label="Dismiss">
              <Icon name="close" size={14} />
            </button>
          </div>
        )}
        {!loaded ? null : creating || !project ? (
          <NewProject catalog={catalog} busy={busy} first={projects.length === 0} onCreate={create} />
        ) : (
          <>
            <header className="project-head">
              <div className="project-title">
                <h2 className="project-name">{project.name}</h2>
                <div className="views" role="group" aria-label="Project views">
                  {(
                    [
                      ["phase", "Phases", "list"],
                      ["trace", "Traceability", "matrix"],
                      ["activity", "Activity", "sparkle"],
                    ] as const
                  ).map(([v, label, icon]) => (
                    <button key={v} type="button" aria-pressed={view === v} disabled={busy} onClick={() => setView(v)}>
                      <Icon name={icon} size={14} />
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <Pipeline phases={project.phases} selected={view === "phase" ? phaseId : null} onSelect={(id) => goToPhase(id)} disabled={busy} />
            </header>

            {view === "trace" && (
              <TraceView trace={trace} phases={project.phases} busy={busy} onOpenRequirement={openRequirement} onOpenArtifact={openArtifact} />
            )}
            {view === "activity" && <ActivityView events={events} phases={project.phases} />}
            {view === "phase" && info && index >= 0 && (
              <PhaseWorkspace
                key={`${project.id}-${phaseId}`}
                projectId={project.id}
                index={index}
                info={info}
                state={project.phases[index]}
                all={project.phases}
                messages={messages}
                events={events.filter((e) => e.phase === phaseId)}
                artifacts={artifacts}
                trace={trace}
                canRender={health?.renderer ?? false}
                busy={busy}
                focus={focus}
                initialValues={prefill?.project === project.id ? prefill.values : undefined}
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
                onOpenRequirement={openRequirement}
                onOpenArtifact={(aid) => openArtifact(aid)}
                onOpenTrace={() => setView("trace")}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}
