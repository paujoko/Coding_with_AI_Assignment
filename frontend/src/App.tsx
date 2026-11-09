import { useCallback, useEffect, useRef, useState } from "react";
import { API_VERSION, api, ApiError } from "./api/client";
import { focusPhase } from "./lib/status";
import type { ActivityEvent, Artifact, Attachment, Health, Message, PhaseInfo, Project, Trace } from "./api/types";
import { ActivityView } from "./components/ActivityView";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { HowItWorks } from "./components/HowItWorks";
import { Icon } from "./components/Icon";
import { NewProject } from "./components/NewProject";
import type { Values } from "./components/Composer";
import { type Focus, PhaseWorkspace } from "./components/PhaseWorkspace";
import { Sidebar, type View } from "./components/Sidebar";
import { SettingsView } from "./components/SettingsView";
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


export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<PhaseInfo[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [project, setProject] = useState<Project | null>(null);
  const [creating, setCreating] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const toggleHelp = (open: boolean) => setHelpOpen(open);
  const [view, setView] = useState<View>("phase");
  const [phaseId, setPhaseId] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [documents, setDocuments] = useState<Attachment[]>([]);
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
    setSettingsOpen(false);
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
    setDocuments([]);
    if (project) api.attachments(project.id).then(setDocuments, () => undefined);
  }, [project?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = useCallback(async (file: File) => {
    const pid = shown.current.project;
    if (!pid) throw new Error("No project open.");
    const att = await api.upload(pid, file);
    if (shown.current.project === pid) setDocuments((ds) => [...ds, att]);
    return att;
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

  const create = (name: string, description: string, files: File[] = []) =>
    guarded(async () => {
      const p = await api.createProject(name);
      setProjects((ps) => [...ps, p]);
      open(p, "requirements");
      // Documents from the start page go up first, so the analyst reads them with the description.
      const attached: Attachment[] = [];
      for (const f of files) attached.push(await api.upload(p.id, f));
      setDocuments(attached);
      if (description) {
        // The developer already said what they want: hand it to the analyst right away.
        // If that fails, the description waits in the composer of the new project.
        setPrefill({ project: p.id, values: { "start.description": description } });
        const r = await api.run(
          p.id,
          "requirements",
          "start",
          { description },
          attached.map((a) => a.id),
        );
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
        project={project}
        creating={creating}
        busy={busy}
        health={health}
        view={view}
        phaseId={phaseId}
        helpOpen={helpOpen}
        settingsOpen={settingsOpen}
        onPick={(id) => {
          const p = projects.find((x) => x.id === id);
          if (p) open(p);
        }}
        onNew={() => {
          setSettingsOpen(false);
          setCreating(true);
        }}
        onPhase={(id) => {
          setSettingsOpen(false);
          goToPhase(id);
        }}
        onView={(v) => {
          setSettingsOpen(false);
          setView(v);
        }}
        onHelp={() => toggleHelp(!helpOpen)}
        onSettings={() => setSettingsOpen(!settingsOpen)}
      />
      {helpOpen && project && !creating && !settingsOpen && <HowItWorks onClose={() => toggleHelp(false)} />}
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
        {health && health.api_version !== API_VERSION && (
          <div className="alert alert-warn" role="alert">
            <Icon name="alert" />
            <p>
              The backend runs older code than this interface. Stop it (Ctrl+C in its window) and start it again, then reload this page.
            </p>
          </div>
        )}
        {health?.llm_ready === false && !settingsOpen && (
          <div className="alert alert-warn" role="alert">
            <Icon name="alert" />
            <p>The agents have no API key yet, so they cannot answer. Paste your key in Settings.</p>
            <button type="button" className="button" onClick={() => setSettingsOpen(true)}>
              Open settings
            </button>
          </div>
        )}
        <ErrorBoundary
          resetKey={`${settingsOpen}-${creating}-${project?.id}-${view}-${phaseId}`}
          onHome={() => {
            setView("phase");
            if (project) setPhaseId(focusPhase(project.phases).id);
          }}
        >
          {!loaded ? null : settingsOpen ? (
            <SettingsView onSaved={() => api.health().then(setHealth, () => undefined)} />
          ) : creating || !project ? (
            <NewProject busy={busy} onCreate={create} />
          ) : (
            <>

              {view === "trace" && (
                <TraceView
                  trace={trace}
                  phases={project.phases}
                  busy={busy}
                  onOpenRequirement={openRequirement}
                  onOpenArtifact={openArtifact}
                />
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
                  documents={documents}
                  onUpload={upload}
                  onRun={(action, input, attachments) =>
                    guarded(async () => {
                      const r = await api.run(project.id, info.id, action, input, attachments);
                      await refresh(r.project);
                    })
                  }
                  onApprove={() => guarded(async () => refresh(await api.approve(project.id, info.id)))}
                  onReopen={() => guarded(async () => refresh(await api.reopen(project.id, info.id)))}
                  onNext={(id) => goToPhase(id)}
                  onSaveContent={async (aid, content) => {
                    await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { content })).project), true);
                  }}
                  onSaveText={async (aid, text) => {
                    await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { text })).project), true);
                  }}
                  onOpenRequirement={openRequirement}
                  onOpenArtifact={(aid) => openArtifact(aid)}
                  onOpenTrace={() => setView("trace")}
                onSetupDiagrams={() => setSettingsOpen(true)}
                />
              )}
            </>
          )}
        </ErrorBoundary>
      </main>
    </div>
  );
}
