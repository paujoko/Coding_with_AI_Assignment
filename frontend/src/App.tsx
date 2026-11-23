import { useCallback, useEffect, useRef, useState } from "react";
import { API_VERSION, api, ApiError } from "./api/client";
import { autoAdvanceTarget, staleOf } from "./lib/next";
import { focusPhase } from "./lib/status";
import { useCarry } from "./lib/useCarry";
import { useUpdate } from "./lib/useUpdate";
import type { ActivityEvent, Artifact, Attachment, Change, DesignCheck, FolderImport, FolderStatus, Health, Message, PhaseInfo, Project, Trace } from "./api/types";
import { ActivityView } from "./components/ActivityView";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { FolderView } from "./components/FolderView";
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
  const [lens, setLens] = useState<string | null>(null); // Traceability: the requirement whose story is open
  const [messages, setMessages] = useState<Message[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [designCheck, setDesignCheck] = useState<DesignCheck | null>(null); // code generation only: does the code fit the design?
  const [changes, setChanges] = useState<Change[]>([]); // Maintenance: changes carried through the phases, newest first
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [documents, setDocuments] = useState<Attachment[]>([]);
  const [folder, setFolder] = useState<FolderStatus | null>(null); // the project's folder and what changed there by hand
  const [folderResult, setFolderResult] = useState<FolderImport | null>(null);
  const [busy, setBusy] = useState(false); // this page sent a request and waits for it
  const [busySince, setBusySince] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // What a phase's composer starts with: a description that still has to be sent, or a next step an agent proposed.
  const [prefill, setPrefill] = useState<{ project: string; phase?: string; action?: string; values: Values } | null>(null);

  // What the screen shows right now. Responses that arrive for another project or phase are dropped,
  // so a slow request can never paint its data into the phase the developer moved to.
  const shown = useRef<{ project: string | null; phase: string | null }>({ project: null, phase: null });
  shown.current = { project: project?.id ?? null, phase: phaseId };

  // The default folder for a new project; a backend without the endpoint simply gives no suggestion.
  const suggestFolder = useCallback((name: string) => api.defaultFolder(name).then((r) => r.path || null, () => null), []);

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : String(e));
  // An agent may also be working on a request this page did not send (sent before a reload, or from another tab).
  // The backend says so (API 7), and the page waits instead of letting the developer send it again (real run s03).
  const remote = busy ? null : (project?.running ?? null);
  const working = busy || remote !== null;
  const since = busy ? busySince : (remote?.started_at ?? null);

  const open = (p: Project, phase?: string) => {
    if (p.id !== project?.id) setEvents([]);
    if (p.id !== project?.id) setLens(null);
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
    const [m, a, t, d, ch] = await Promise.all([
      api.messages(pid, phase),
      api.artifacts(pid, phase),
      api.trace(pid),
      phase === "codegen" ? api.designCheck(pid).catch(() => null) : Promise.resolve(null),
      phase === "maintenance" ? api.changes(pid) : Promise.resolve([] as Change[]),
    ]);
    if (shown.current.project !== pid || shown.current.phase !== phase) return;
    setMessages(m);
    setArtifacts(a);
    setTrace(t);
    setChanges(ch);
    setDesignCheck(d);
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

  // The project's folder (ADR 0015): what the developer changed there by hand. Looked at when the project opens,
  // after every change, when the window gets focus again (back from the editor) and every few seconds.
  const loadFolder = useCallback(async (pid: string) => {
    const status = await api.folder(pid);
    if (shown.current.project === pid) setFolder(status);
  }, []);

  useEffect(() => {
    setFolder(null);
    setFolderResult(null);
    if (project) loadFolder(project.id).catch(() => undefined);
  }, [project?.id, loadFolder]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!project?.folder?.path || working) return;
    const pid = project.id;
    const look = () => loadFolder(pid).catch(() => undefined);
    const id = window.setInterval(look, 8000);
    window.addEventListener("focus", look);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("focus", look);
    };
  }, [project?.id, project?.folder?.path, working, loadFolder]); // eslint-disable-line react-hooks/exhaustive-deps

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
    const id = window.setInterval(tick, working ? 600 : 3000);
    tick();
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [project?.id, working, events.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // While an agent works on a request this page did not send, ask the backend until it has finished, then reload.
  useEffect(() => {
    if (!project || !remote) return;
    const id = window.setInterval(async () => {
      const p = await api.project(project.id).catch(() => null);
      if (!p || shown.current.project !== p.id) return;
      if (p.running) setProject(p);
      else await refresh(p).catch(fail);
    }, 2000);
    return () => window.clearInterval(id);
  }, [project?.id, remote?.started_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = async (p: Project) => {
    setProject(p);
    setProjects((ps) => ps.map((x) => (x.id === p.id ? p : x)));
    if (shown.current.phase) await loadPhase(p.id, shown.current.phase);
    await loadFolder(p.id).catch(() => undefined);
  };

  // Returns whether the work succeeded. rethrow: editors keep the developer's unsaved text when a save fails.
  // Navigation is disabled while busy, so project and phase cannot change under a running request.
  const guarded = async (work: () => Promise<void>, rethrow = false): Promise<boolean> => {
    setBusy(true);
    setBusySince(new Date().toISOString());
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
      setBusySince(null);
    }
  };

  // A change carried through the phases (Maintenance). One guarded request per press, so the app is busy for the
  // whole run: navigation is off and nothing else can be sent. After every phase the project, the phase data and
  // the trace are loaded again. A refused request (409 while another action runs) is told in the tracker.
  const carry = useCarry({
    projectId: project?.id ?? null,
    guarded,
    advance: api.advanceChange,
    onAdvanced: async (r) => {
      if (shown.current.project !== r.project.id) return;
      setChanges((cs) => cs.map((c) => (c.number === r.change.number ? r.change : c)));
      await refresh(r.project);
    },
    onFailed: async (pid) => {
      const p = await api.project(pid);
      if (shown.current.project === pid) await refresh(p);
    },
  });

  // "Update all N steps" (API 10): one phase per call, the app is busy for the whole run. After every call the
  // project, the phase data and the trace are loaded again, so the screen follows what was updated.
  const update = useUpdate({
    projectId: project?.id ?? null,
    guarded,
    catchUp: api.catchUp,
    titleOf: (id) => project?.phases.find((x) => x.id === id)?.title ?? catalog.find((x) => x.id === id)?.title ?? id,
    onResult: async (r) => {
      if (shown.current.project !== r.project.id) return;
      await refresh(r.project);
    },
    onFailed: async (pid) => {
      const p = await api.project(pid);
      if (shown.current.project === pid) await refresh(p);
    },
  });

  const create = (name: string, description: string, files: File[] = [], folderPath = "") =>
    guarded(async () => {
      const p = await api.createProject(name, folderPath);
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
        await loadFolder(p.id).catch(() => undefined);
      }
    });

  // Navigation waits while an agent works, so its result lands in the phase that asked for it.
  const goToPhase = (phase: string, f: Focus = {}) => {
    if (working) return;
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
        busy={working}
        health={health}
        view={view}
        phaseId={phaseId}
        folderChanges={folder?.changes.length ?? 0}
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
        {remote && (
          <div className="alert alert-warn" role="status">
            <Icon name="spinner" className="spin" />
            <p>
              {remote.label} in {catalog.find((c) => c.id === remote.phase)?.title ?? remote.phase} is still running. This page waits for it.
            </p>
          </div>
        )}
        {project && !creating && !settingsOpen && view !== "folder" && folder?.path && (folder.problem || folder.changes.length > 0) && (
          <div className="alert alert-warn" role="status">
            <Icon name="folder" />
            <p>
              {folder.problem
                ? `Wings cannot write to the folder: ${folder.problem}`
                : `${folder.changes.length} file${folder.changes.length === 1 ? "" : "s"} changed in your folder by hand.`}
            </p>
            <button type="button" className="button" disabled={working} onClick={() => setView("folder")}>
              Review
            </button>
          </div>
        )}
        {project && !creating && !settingsOpen && view !== "folder" && folder !== null && !folder.path && (
          <div className="alert alert-warn" role="status">
            <Icon name="folder" />
            <p>This project has no folder yet.</p>
            <button type="button" className="button" disabled={working} onClick={() => setView("folder")}>
              Choose a folder
            </button>
          </div>
        )}
        {health && health.api_version !== API_VERSION && (
          <div className="alert alert-warn" role="alert">
            <Icon name="alert" />
            <p>
              The backend runs older code than this interface. Restart it, then reload this page.
            </p>
          </div>
        )}
        {health?.llm_ready === false && !settingsOpen && (
          <div className="alert alert-warn" role="alert">
            <Icon name="alert" />
            <p>The agents have no API key yet. Add it in Settings.</p>
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
            <NewProject
              busy={working}
              onCreate={create}
              onBrowse={health?.folder_picker ? (start, name) => api.pickFolder(start, name) : undefined}
              onSuggestFolder={suggestFolder}
            />
          ) : (
            <>

              {view === "trace" && (
                <TraceView
                  trace={trace}
                  phases={project.phases}
                  busy={working}
                  onOpenRequirement={openRequirement}
                  onOpenArtifact={openArtifact}
                  projectId={project.id}
                  canRender={health?.renderer ?? false}
                  requirement={lens}
                  onRequirement={setLens}
                />
              )}
              {view === "activity" && <ActivityView events={events} phases={project.phases} />}
              {view === "folder" && (
                <FolderView
                  status={folder}
                  phases={project.phases}
                  busy={working}
                  result={folderResult}
                  onLink={(path) =>
                    guarded(async () => {
                      const s = await api.setFolder(project.id, path);
                      setFolder(s);
                      if (s.project) await refresh(s.project);
                    })
                  }
                  onUnlink={() =>
                    guarded(async () => {
                      const s = await api.setFolder(project.id, null);
                      setFolderResult(null);
                      if (s.project) await refresh(s.project);
                    })
                  }
                  onImport={(paths) =>
                    guarded(async () => {
                      const r = await api.importFolder(project.id, paths);
                      setFolderResult(r);
                      await refresh(r.project);
                    })
                  }
                  onRestore={(paths) => guarded(async () => setFolder(await api.restoreFolder(project.id, paths)))}
                  onRefresh={() => loadFolder(project.id).catch(fail)}
                  onOpenPhase={(phase) => goToPhase(phase)}
                  onBrowse={health?.folder_picker ? (start) => api.pickFolder(start, project.name) : undefined}
                />
              )}
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
                  designCheck={info.id === "codegen" ? designCheck : null}
                  canRender={health?.renderer ?? false}
                  busy={working}
                  busySince={since}
                  focus={focus}
                  initialValues={prefill?.project === project.id && (!prefill.phase || prefill.phase === phaseId) ? prefill.values : undefined}
                  initialAction={prefill?.project === project.id && prefill.phase === phaseId ? prefill.action : undefined}
                  documents={documents}
                  onUpload={upload}
                  onRun={(action, input, attachments) =>
                    guarded(async () => {
                      const r = await api.run(project.id, info.id, action, input, attachments);
                      setPrefill((x) => (x?.phase === info.id ? null : x));
                      await refresh(r.project);
                    })
                  }
                  onApprove={() =>
                    guarded(async () => {
                      const approved = await api.approve(project.id, info.id);
                      await refresh(approved);
                      // One obvious next step that is ready to start: go there instead of asking for a click.
                      const target = autoAdvanceTarget(approved.phases, info.id);
                      if (target && shown.current.project === approved.id) {
                        setPhaseId(target);
                        setFocus({});
                      }
                    })
                  }
                  onReopen={() => guarded(async () => refresh(await api.reopen(project.id, info.id)))}
                  onNext={(id) => goToPhase(id)}
                  onStep={(next) => {
                    // Open the phase with the proposed input in its composer: the developer reads it and sends it.
                    goToPhase(next.phase);
                    setPrefill({
                      project: project.id,
                      phase: next.phase,
                      action: next.action,
                      values: Object.fromEntries(Object.entries(next.input).map(([k, v]) => [`${next.action}.${k}`, v as Values[string]])),
                    });
                  }}
                  onSaveContent={async (aid, content) => {
                    await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { content })).project), true);
                  }}
                  onSaveText={async (aid, text) => {
                    await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { text })).project), true);
                  }}
                  onOpenRequirement={openRequirement}
                  onOpenArtifact={(aid, phase) => openArtifact(aid, phase)}
                  changes={info.id === "maintenance" ? changes : []}
                  openChange={project.open_change ?? null}
                  carry={carry.run}
                  onAdvance={(change) => void carry.start(change, false)}
                  stale={staleOf(project)}
                  update={update.run}
                  onUpdate={(only) => void update.start(staleOf(project), only)}
                  onStopUpdate={update.requestStop}
                  onOpenTrace={() => setView("trace")}
                  folder={project.folder?.path ?? folder?.path ?? null}
                  onOpenFolder={() => setView("folder")}
                  onRunIt={() => goToPhase("deployment", { artifact: "run-guide" })}
                  onOpenLens={(id) => {
                    if (working) return;
                    setLens(id);
                    setView("trace");
                  }}
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
