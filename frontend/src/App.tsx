import { useCallback, useEffect, useRef, useState } from "react";
import { API_VERSION, api, ApiError } from "./api/client";
import { afterAccept, autoStart, currentStep, redoOf, stepTitle } from "./lib/flow";
import { type Outgoing, outgoing, unsent } from "./lib/outbox";
import { useUpdate } from "./lib/useUpdate";
import { afterWork, follows, moveWork, noticeFor, type Work } from "./lib/work";
import type { ActionResult, ActivityEvent, Artifact, Attachment, Change, DesignCheck, FolderImport, FolderStatus, Health, Message, PhaseInfo, Project, Trace } from "./api/types";
import { ActivityView } from "./components/ActivityView";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { FolderView } from "./components/FolderView";
import { HowItWorks } from "./components/HowItWorks";
import { Icon } from "./components/Icon";
import { NewProject } from "./components/NewProject";
import type { Values } from "./components/Composer";
import { type Focus, PhaseWorkspace } from "./components/PhaseWorkspace";
import { ProgramView } from "./components/ProgramView";
import { RedoStrip } from "./components/RedoStrip";
import { Sidebar, type View } from "./components/Sidebar";
import { SettingsView } from "./components/SettingsView";
import { TraceView } from "./components/TraceView";
import { WorkNotice } from "./components/WorkNotice";

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

/** A redo that stopped because its result now waits for Accept is no news: the screen says so already. */
const waitsForAccept = (p: Project, phase: string) => p.phases.find((x) => x.id === phase)?.status === "draft";

/** The step a project opens on: the one it waits on, else Your program. */
const landing = (p: Project) => currentStep(p.phases, redoOf(p))?.id ?? (p.phases.some((x) => x.id === "maintenance") ? "maintenance" : p.phases[0].id);

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<PhaseInfo[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [project, setProject] = useState<Project | null>(null);
  const [creating, setCreating] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [view, setView] = useState<View>("phase");
  const [phaseId, setPhaseId] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus>({});
  const [lens, setLens] = useState<string | null>(null); // Traceability: the requirement whose story is open
  const [messages, setMessages] = useState<Message[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [deployment, setDeployment] = useState<Artifact[]>([]); // Your program: the run guide and the deployment check
  const [trace, setTrace] = useState<Trace | null>(null);
  const [designCheck, setDesignCheck] = useState<DesignCheck | null>(null);
  const [changes, setChanges] = useState<Change[]>([]); // tracked changes, newest first
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [documents, setDocuments] = useState<Attachment[]>([]);
  const [folder, setFolder] = useState<FolderStatus | null>(null);
  const [folderResult, setFolderResult] = useState<FolderImport | null>(null);
  const [busy, setBusy] = useState(false);
  const [busySince, setBusySince] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null); // why a redo stopped: not an error, something to do
  const [prefill, setPrefill] = useState<{ project: string; phase?: string; action?: string; values: Values } | null>(null);
  // Messages sent but not saved yet (lib/outbox.ts): shown as bubbles at once, "Not sent" when the run failed.
  const [outbox, setOutbox] = useState<Outgoing[]>([]);
  const outboxId = useRef(1);
  // The step an agent works on (lib/work.ts). The developer may look at other steps meanwhile, read-only.
  const [work, setWorkState] = useState<Work | null>(null);
  const workRef = useRef<Work | null>(null);
  const setWork = (w: Work | null) => {
    workRef.current = w;
    setWorkState(w);
  };

  // What the screen shows right now. Responses that arrive for another project or step are dropped.
  const shown = useRef<{ project: string | null; phase: string | null; view: View }>({ project: null, phase: null, view: "phase" });
  shown.current = { project: project?.id ?? null, phase: phaseId, view };

  const suggestFolder = useCallback((name: string) => api.defaultFolder(name).then((r) => r.path || null, () => null), []);

  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : String(e));
  const remote = busy ? null : (project?.running ?? null);
  const working = busy || remote !== null;
  const since = busy ? busySince : (remote?.started_at ?? null);
  const openChange = changes.find((c) => c.state === "open") ?? null;
  const redo = project ? redoOf(project, openChange) : [];
  const titleOf = (id: string) => stepTitle(project?.phases.find((x) => x.id === id) ?? catalog.find((x) => x.id === id) ?? { id });

  const open = (p: Project, phase?: string) => {
    if (p.id !== project?.id) {
      setEvents([]);
      setLens(null);
      if (workRef.current?.state !== "running") setWork(null);
    }
    setProject(p);
    setCreating(false);
    setSettingsOpen(false);
    setView("phase");
    setPhaseId(phase ?? landing(p));
    setFocus({});
    setNotice(null);
    remember(p.id);
  };

  // The tab shows the open project; the tool itself carries no name, only its logo.
  useEffect(() => {
    document.title = project?.name ?? "Projects";
  }, [project?.name]);

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
    const program = phase === "maintenance";
    const [m, a, t, d, ch, dep] = await Promise.all([
      api.messages(pid, phase),
      api.artifacts(pid, phase),
      api.trace(pid),
      phase === "codegen" || program ? api.designCheck(pid).catch(() => null) : Promise.resolve(null),
      api.changes(pid).catch(() => [] as Change[]), // an open change decides which steps follow it, on every step
      program ? api.artifacts(pid, "deployment").catch(() => [] as Artifact[]) : Promise.resolve([] as Artifact[]),
    ]);
    if (shown.current.project !== pid || shown.current.phase !== phase) return;
    setMessages(m);
    setArtifacts(a);
    setTrace(t);
    setChanges(ch);
    setDesignCheck(d);
    setDeployment(dep);
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

  // The project's folder (ADR 0015): what the developer changed there by hand.
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

  /**
   * Runs one request at a time. `step`: the step the agent works on (the one on screen when it was asked); the
   * developer may look at other steps meanwhile, and a notice there leads back. Without it (folder, delete) no
   * step is marked as working.
   */
  const guarded = async (job: () => Promise<void>, opts: { rethrow?: boolean; step?: string | null } = {}): Promise<boolean> => {
    setBusy(true);
    setBusySince(new Date().toISOString());
    setError(null);
    setNotice(null);
    const pid = shown.current.project;
    if (opts.step && pid) setWork({ project: pid, phase: opts.step, state: "running" });
    let ok = false;
    try {
      await job();
      ok = true;
      return true;
    } catch (e) {
      fail(e);
      const { project: shownProject, phase } = shown.current;
      if (shownProject && phase) await loadPhase(shownProject, phase).catch(() => undefined);
      if (opts.rethrow) throw e;
      return false;
    } finally {
      // Wings does not jump to the step when it is done: the notice says it is ready.
      if (workRef.current?.state === "running") setWork(afterWork(workRef.current, ok, shown.current));
      setBusy(false);
      setBusySince(null);
    }
  };

  /**
   * The work goes on in another step (Accept starts the next one, Redo all takes the next stale step). The screen
   * moves with it only when the developer watches the working step; refresh and loadPhase read the ref.
   */
  const show = (phase: string) => {
    const follow = follows(workRef.current, shown.current);
    setWork(moveWork(workRef.current, phase));
    if (!follow) return;
    shown.current = { ...shown.current, phase, view: "phase" };
    setView("phase");
    setPhaseId(phase);
    setFocus({});
  };

  /**
   * Run one action. If it carries the developer's words, they show at once as a bubble (the backend saves them only
   * with the agent's reply). On failure the bubble stays "Not sent" and the words wait in the step's text box.
   */
  const runTracked = async (pid: string, phase: string, action: string, input: Record<string, unknown>, attachments: string[] = [], known: Attachment[] = documents): Promise<ActionResult> => {
    const spec = catalog.find((c) => c.id === phase)?.actions.find((a) => a.name === action);
    const o = outgoing({
      id: outboxId.current++,
      project: pid,
      phase,
      action: spec,
      input,
      attachments,
      documents: known,
      seen: project?.id === pid && shown.current.project === pid && shown.current.phase === phase ? messages : [],
      now: new Date().toISOString(),
    });
    // A new message in a step replaces one that was not sent: the developer has moved on.
    if (o) setOutbox((xs) => [...xs.filter((x) => !(x.project === pid && x.phase === phase)), o]);
    let r: ActionResult;
    try {
      r = await api.run(pid, phase, action, input, attachments);
    } catch (e) {
      if (o) {
        setOutbox((xs) => xs.map((x) => (x.id === o.id ? { ...x, state: "failed" } : x)));
        const field = spec?.message_field;
        if (field && typeof input[field] === "string") setPrefill({ project: pid, phase, action, values: { [`${action}.${field}`]: input[field] as string } });
      }
      throw e;
    }
    setPrefill((x) => (x?.project === pid && x.phase === phase ? null : x));
    await refresh(r.project);
    if (o) setOutbox((xs) => xs.filter((x) => x.id !== o.id));
    return r;
  };

  // A "ready" notice has done its job once the developer opens that step.
  useEffect(() => {
    if (work && work.state !== "running" && view === "phase" && phaseId === work.phase) setWork(null);
  }, [work, view, phaseId]); // eslint-disable-line react-hooks/exhaustive-deps

  // "Redo all, accept when checks pass": the loop over POST /catch-up with approval (ADR 0016).
  const update = useUpdate({
    projectId: project?.id ?? null,
    // Started from a step screen: that step counts as working first, so the screen follows the loop step by step
    // while the developer watches it, and stays put once they look elsewhere.
    guarded: (job) => guarded(job, { step: shown.current.view === "phase" ? shown.current.phase : (redo[0] ?? null) }),
    catchUp: api.catchUp,
    titleOf,
    onResult: async (r) => {
      if (shown.current.project !== r.project.id) return;
      const now = r.remaining[0] ?? r.ran[0]?.phase;
      if (now) show(now);
      await refresh(r.project);
    },
    onFailed: async (pid) => {
      const p = await api.project(pid);
      if (shown.current.project === pid) await refresh(p);
    },
  });

  /** Redo the first step that has to follow a change. It is made again and waits for Accept. */
  const redoFirst = async (pid: string, first: string) => {
    show(first);
    // A step that is out of date is brought up to date by catch-up; a step an open change has not reached yet
    // (nothing is stale before the change touches the requirements) by one step of that change. No approval.
    const [p, cs] = await Promise.all([api.project(pid), api.changes(pid).catch(() => [] as Change[])]);
    const open = cs.find((c) => c.state === "open");
    const stale = redoOf(p).includes(first);
    if (!stale && open) {
      const r = await api.advanceChange(pid, open.number, false);
      if (shown.current.project !== pid) return;
      await refresh(r.project);
      if (r.stopped_reason && !waitsForAccept(r.project, first)) setNotice(r.stopped_reason);
      return;
    }
    const r = await api.catchUp(pid, false);
    if (shown.current.project !== pid) return;
    await refresh(r.project);
    if (r.stopped_reason && !waitsForAccept(r.project, first)) setNotice(r.stopped_reason);
  };

  /** Accept: approve the step, then the next one (lib/flow.ts afterAccept). One click per step. */
  const accept = (phase: string) => {
    if (!project) return;
    const pid = project.id;
    return guarded(async () => {
      const approved = await api.approve(pid, phase);
      await refresh(approved);
      if (shown.current.project !== pid) return;
      const cs = await api.changes(pid).catch(() => [] as Change[]);
      const after = afterAccept(approved.phases, redoOf(approved, cs.find((c) => c.state === "open")), phase, catalog);
      if (after.kind === "done") return show("maintenance");
      if (after.kind === "redo") return redoFirst(pid, after.phase);
      show(after.phase); // "choose" and "open": the step's screen asks the developer first
      if (after.kind === "make") {
        const action = autoStart(catalog.find((c) => c.id === after.phase));
        if (!action) return;
        const r = await api.run(pid, after.phase, action, {});
        if (shown.current.project === pid) await refresh(r.project);
      }
    }, { step: phase });
  };

  const create = (name: string, description: string, files: File[] = [], folderPath = "") =>
    guarded(async () => {
      const p = await api.createProject(name, folderPath);
      setProjects((ps) => [...ps, p]);
      open(p, "requirements");
      shown.current = { project: p.id, phase: "requirements", view: "phase" };
      setWork({ project: p.id, phase: "requirements", state: "running" });
      const attached: Attachment[] = [];
      for (const f of files) attached.push(await api.upload(p.id, f));
      setDocuments(attached);
      // The description shows at once as the first message; if the start fails it waits in the start composer.
      if (description) await runTracked(p.id, "requirements", "start", { description }, attached.map((a) => a.id), attached);
    });

  // Wings forgets the project; its folder stays. The current one gives way to the newest other project.
  const removeProject = (id: string) =>
    guarded(async () => {
      await api.deleteProject(id);
      const rest = projects.filter((x) => x.id !== id);
      setProjects(rest);
      if (project?.id !== id) return;
      const next = rest[rest.length - 1];
      if (next) open(next);
      else {
        setProject(null);
        setPhaseId(null);
        setEvents([]);
        setCreating(true);
      }
    });

  // Navigation works while an agent works: other steps are read-only meanwhile, and the result is saved by the
  // backend whatever is on screen (loadPhase drops responses for a step that is no longer shown).
  const goToPhase = (phase: string, f: Focus = {}) => {
    setNotice(null);
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
        <h1>The backend cannot be reached</h1>
        <p>{error}</p>
        <p>
          Start it from <code>backend/</code> with <code>python -m uvicorn wings.main:app --port 8810</code>, then reload this page.
        </p>
      </main>
    );
  }

  const index = project && phaseId ? project.phases.findIndex((p) => p.id === phaseId) : -1;
  const info = catalog.find((c) => c.id === phaseId);
  const running = busy ? (work?.state === "running" ? work.phase : null) : (remote?.phase ?? null);
  const inProject = project && !creating && !settingsOpen;
  const runPhase = (pid: string, phase: string, action: string, input: Record<string, unknown>, attachments: string[] = []) =>
    guarded(async () => void (await runTracked(pid, phase, action, input, attachments)), { step: phase });
  // This step's bubbles that are not saved yet.
  const pendingIn = (phase: string) => (project ? unsent(messages, outbox.filter((o) => o.project === project.id && o.phase === phase)) : []);
  // The notice above every screen but the working step (lib/work.ts).
  const workNotice = inProject && work?.project === project?.id ? noticeFor(work, { view, phase: phaseId }) : null;

  /** Your program: a change runs, then Wings writes its first step (the requirements) at once and opens it. */
  const runProgram = (pid: string, action: string, input: Record<string, unknown>) =>
    guarded(async () => {
      const r = await runTracked(pid, "maintenance", action, input);
      // A change revises the requirements and marks later steps for a redo: go where it waits.
      if (action !== "change" || r.project.phases.find((x) => x.id === "maintenance")?.status === "needs_input") return;
      const open = (await api.changes(pid)).find((c) => c.state === "open");
      if (!open || shown.current.project !== r.project.id) return;
      setChanges((cs) => [open, ...cs.filter((c) => c.number !== open.number)]);
      if (open.next?.kind === "run") {
        show(open.next.phase);
        const a = await api.advanceChange(pid, open.number, false);
        await refresh(a.project);
        if (a.stopped_reason) setNotice(a.stopped_reason);
      } else if (open.next) show(open.next.phase);
    }, { step: "maintenance" });

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
        redo={redo}
        running={running}
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
        onDelete={removeProject}
        onPhase={(id) => {
          setSettingsOpen(false);
          goToPhase(id);
        }}
        onView={(v) => {
          setSettingsOpen(false);
          setView(v);
        }}
        onHelp={() => setHelpOpen(!helpOpen)}
        onSettings={() => setSettingsOpen(!settingsOpen)}
      />
      {helpOpen && inProject && <HowItWorks onClose={() => setHelpOpen(false)} />}
      <main className="main">
        {workNotice && work && (
          <WorkNotice title={titleOf(workNotice.phase)} state={workNotice.state} since={busySince} onShow={() => goToPhase(work.phase)} />
        )}
        {error && (
          <div className="alert" role="alert">
            <Icon name="alert" />
            <p>{error}</p>
            <button type="button" className="icon-button" onClick={() => setError(null)} aria-label="Dismiss">
              <Icon name="close" size={14} />
            </button>
          </div>
        )}
        {remote && (
          <div className="alert alert-quiet" role="status">
            <Icon name="spinner" className="spin" />
            <p>
              {remote.label} in {titleOf(remote.phase)} is still running. This page waits for it.
            </p>
          </div>
        )}
        {inProject && view !== "folder" && folder?.path && (folder.problem || folder.changes.length > 0) && (
          <div className="alert alert-quiet" role="status">
            <Icon name="folder" />
            <p>
              {folder.problem
                ? `Cannot write to the folder: ${folder.problem}`
                : `You changed ${folder.changes.length} file${folder.changes.length === 1 ? "" : "s"} in the project folder.`}
            </p>
            <button type="button" className="button" onClick={() => setView("folder")}>
              Review
            </button>
          </div>
        )}
        {health && health.api_version !== API_VERSION && (
          <div className="alert" role="alert">
            <Icon name="alert" />
            <p>The backend runs older code than this interface. Restart it, then reload this page.</p>
          </div>
        )}
        {health?.llm_ready === false && !settingsOpen && (
          <div className="alert" role="alert">
            <Icon name="alert" />
            <p>The agents have no API key yet. Add it in Settings.</p>
            <button type="button" className="button" onClick={() => setSettingsOpen(true)}>
              Open settings
            </button>
          </div>
        )}
        {inProject && view === "phase" && project && (
          <RedoStrip
            redo={redo}
            all={project.phases}
            busy={working}
            run={update.run}
            current={phaseId}
            onRest={() => void update.start(redo)}
            onStop={update.requestStop}
            onGo={(id) => goToPhase(id)}
          />
        )}
        {notice && !working && (
          <div className="alert alert-quiet" role="status">
            <Icon name="alert" />
            <p>{notice}</p>
            <button type="button" className="icon-button" onClick={() => setNotice(null)} aria-label="Dismiss">
              <Icon name="close" size={14} />
            </button>
          </div>
        )}
        <ErrorBoundary
          resetKey={`${settingsOpen}-${creating}-${project?.id}-${view}-${phaseId}`}
          onHome={() => {
            setView("phase");
            if (project) setPhaseId(landing(project));
          }}
        >
          {!loaded ? (
            <p className="working boot-loading" role="status">
              <Icon name="spinner" className="spin" />
              Opening
            </p>
          ) : settingsOpen ? (
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
              {view === "phase" && info && index >= 0 && info.id === "maintenance" && (
                <ProgramView
                  key={project.id}
                  info={info}
                  state={project.phases[index]}
                  all={project.phases}
                  redo={redo}
                  messages={messages}
                  events={events.filter((e) => e.phase === "maintenance")}
                  artifacts={artifacts}
                  runGuide={deployment.find((a) => a.kind === "run_guide" && !a.retired) ?? null}
                  deployCheck={deployment.find((a) => a.kind === "deployment_check" && !a.retired) ?? null}
                  trace={trace}
                  designCheck={designCheck}
                  changes={changes}
                  busy={working}
                  busySince={since}
                  running={running}
                  pending={pendingIn("maintenance")}
                  folder={project.folder?.path ?? folder?.path ?? null}
                  initialValues={prefill?.project === project.id && prefill.phase === "maintenance" ? prefill.values : undefined}
                  onRun={(action, input) => runProgram(project.id, action, input)}
                  onRetry={(o) => runProgram(o.project, o.action, o.input)}
                  onProbe={() => void runPhase(project.id, "testing", "probe", {})}
                  onGo={(id) => goToPhase(id)}
                  onStep={(next) => {
                    goToPhase(next.phase);
                    setPrefill({
                      project: project.id,
                      phase: next.phase,
                      action: next.action,
                      values: Object.fromEntries(Object.entries(next.input).map(([k, v]) => [`${next.action}.${k}`, v as Values[string]])),
                    });
                  }}
                  onOpenFolder={() => setView("folder")}
                  onOpenRequirement={openRequirement}
                  onOpenArtifact={openArtifact}
                />
              )}
              {view === "phase" && info && index >= 0 && info.id !== "maintenance" && (
                <PhaseWorkspace
                  key={`${project.id}-${phaseId}`}
                  projectId={project.id}
                  info={info}
                  catalog={catalog}
                  state={project.phases[index]}
                  all={project.phases}
                  redo={redo}
                  messages={messages}
                  events={events.filter((e) => e.phase === phaseId)}
                  artifacts={artifacts}
                  trace={trace}
                  designCheck={info.id === "codegen" ? designCheck : null}
                  canRender={health?.renderer ?? false}
                  busy={working}
                  busySince={since}
                  running={running}
                  pending={pendingIn(info.id)}
                  onRetry={(o) => runPhase(o.project, o.phase, o.action, o.input, o.attachments)}
                  focus={focus}
                  initialValues={prefill?.project === project.id && (!prefill.phase || prefill.phase === phaseId) ? prefill.values : undefined}
                  initialAction={prefill?.project === project.id && prefill.phase === phaseId ? prefill.action : undefined}
                  documents={documents}
                  onUpload={upload}
                  onRun={(action, input, attachments) => runPhase(project.id, info.id, action, input, attachments)}
                  onAccept={() => void accept(info.id)}
                  onRedo={() => void guarded(() => redoFirst(project.id, info.id), { step: info.id })}
                  onKeep={() => void guarded(async () => refresh(await api.approve(project.id, info.id)), { step: info.id })}
                  onGo={(id) => goToPhase(id)}
                  onStep={(next) => {
                    goToPhase(next.phase);
                    setPrefill({
                      project: project.id,
                      phase: next.phase,
                      action: next.action,
                      values: Object.fromEntries(Object.entries(next.input).map(([k, v]) => [`${next.action}.${k}`, v as Values[string]])),
                    });
                  }}
                  onSaveContent={async (aid, content) => {
                    await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { content })).project), { rethrow: true, step: info.id });
                  }}
                  onSaveText={async (aid, text) => {
                    await guarded(async () => refresh((await api.updateArtifact(project.id, aid, { text })).project), { rethrow: true, step: info.id });
                  }}
                  onOpenRequirement={openRequirement}
                  onOpenArtifact={(aid, phase) => openArtifact(aid, phase)}
                  onOpenTrace={() => setView("trace")}
                  folder={project.folder?.path ?? folder?.path ?? null}
                  onOpenFolder={() => setView("folder")}
                  onOpenLens={(id) => {
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
