import { useCallback, useEffect, useRef, useState } from "react";
import type { ActivityEvent, Artifact, Attachment, Change, DesignCheck, Gap, Message, NextAction, OpenChange, PhaseInfo, PhaseState, Trace } from "../api/types";
import { formatSize, usePendingFiles } from "../lib/attachments";
import { type CarryRun, changeLine, maintenanceWord } from "../lib/changes";
import { agentLabel } from "../lib/format";
import { CheckedByCode } from "./CheckedByCode";
import { displayStatus, readyToRun, statusHint } from "../lib/status";
import { Composer, type Values } from "./Composer";
import { Conversation } from "./Conversation";
import { DeploymentCheckView } from "./DeploymentCheckView";
import { DesignView } from "./DesignView";
import { DropZone } from "./DropZone";
import { FilesView } from "./FilesView";
import { Icon } from "./Icon";
import { ChangeDockNote, ChangeTracker } from "./ChangeTracker";
import { ChangesView, ConsistencyView, MaintenanceStart } from "./MaintenanceViews";
import { RequirementsView } from "./RequirementsView";
import { ReviewView } from "./ReviewView";
import { RunGuideView } from "./RunGuideView";
import { Splitter } from "./Splitter";
import { StatusBadge } from "./StatusBadge";
import { TestReportView } from "./TestReportView";
import { TestStrengthView } from "./TestStrengthView";

export type Focus = { requirement?: string; artifact?: string };

interface Props {
  projectId: string;
  index: number;
  info: PhaseInfo;
  state: PhaseState;
  all: PhaseState[];
  messages: Message[];
  events: ActivityEvent[];
  artifacts: Artifact[];
  trace: Trace | null;
  designCheck?: DesignCheck | null; // code generation: the code against the current class diagram, checked by code
  canRender: boolean;
  busy: boolean;
  busySince?: string | null; // when the running agent action started (ISO), for the elapsed time
  focus: Focus;
  initialValues?: Values; // e.g. the description of a create-and-start whose start failed
  initialAction?: string; // the action a next step from another phase opens
  onRun: (action: string, input: Record<string, unknown>, attachments: string[]) => Promise<boolean>;
  documents: Attachment[]; // everything uploaded to the project
  onUpload: (file: File) => Promise<Attachment>;
  onApprove: () => void;
  onReopen: () => void;
  onNext: (phase: string) => void;
  onStep: (step: NextAction) => void; // a next step an agent proposed for another phase
  onSaveContent: (artifactId: string, content: Record<string, unknown>) => Promise<void>;
  onSaveText: (artifactId: string, text: string) => Promise<void>;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase?: string) => void;
  onOpenTrace: () => void;
  onSetupDiagrams: () => void; // open Settings when pictures are not set up
  // Maintenance: changes carried through the phases (API 9).
  changes?: Change[]; // tracked changes, newest first
  openChange?: OpenChange | null; // the change in progress, from the project
  carry?: CarryRun | null; // the run the tracker started, live and after it stopped
  onAdvance?: (change: Change, through: boolean) => void; // one step, or carry it through
  onStopCarry?: () => void;
  folder?: string | null; // the project's folder, for the commands of the "Run it" card
  onOpenFolder?: () => void;
  onRunIt?: () => void; // open the "Run it" card of Deployment
  onOpenLens?: (requirementId: string) => void; // one requirement through design, code and tests (Traceability)
}

const CHAT_WIDTH = "wings.chatWidth";

function storedWidth(): number | null {
  try {
    const v = Number(localStorage.getItem(CHAT_WIDTH));
    return v > 0 ? v : null;
  } catch {
    return null;
  }
}

// Read diagrams from the outside in: goals, then structure, then behaviour, then runtime.
const DIAGRAM_ORDER = ["use_case", "class", "sequence", "activity", "state", "component", "deployment"];
const rank = (a: Artifact) => DIAGRAM_ORDER.indexOf(a.content.kind);

// One line for an empty conversation: what this step does.
const EMPTY_OUTPUT: Record<string, string> = {
  requirements: "Describe the software. The analyst turns it into numbered requirements.",
  design: "The architect draws the diagrams from the approved requirements.",
  refinement: "A reviewer checks the design and lists what to improve.",
  codegen: "The coder writes the code from the approved design.",
  testing: "The tester writes a test for every acceptance criterion and runs them.",
  deployment: "Deployment files are written, checked and started once.",
  maintenance: "Describe a change or a bug to see what it touches.",
};

const FILE_TITLE = { source_file: "Code", test_file: "Tests", deployment_file: "Deployment files" };

// Run the phase's deterministic step again (Run tests, Check again): no input, no model writing anything new.
export function rerunAction(info: PhaseInfo): PhaseInfo["actions"][number] | undefined {
  return info.actions.find((a) => (a.name === "run" || a.name === "check") && !a.message_field && Object.keys(a.input_schema.properties ?? {}).length === 0);
}

// The action a phase most likely needs next. Once a phase has output, typed text should not silently start
// the generator again (session s04: "run the tests" typed with Write tests selected wrote 40 new tests).
export function preferredAction(info: PhaseInfo, state: PhaseState): string {
  const has = (name: string) => info.actions.some((a) => a.name === name);
  const rerun = rerunAction(info)?.name;
  if (state.status === "needs_input" && has("answer")) return "answer";
  if (state.status === "stale" && rerun) return rerun;
  if ((state.status === "draft" || state.status === "approved" || state.status === "stale") && has("revise")) return "revise";
  if ((state.status === "draft" || state.status === "approved") && rerun) return rerun;
  return info.actions[0]?.name ?? "";
}

// "Q1: Command line" lines in the answer field <-> chosen options on the question cards.
function parseAnswers(text: Values[string] | undefined): Record<string, string> {
  if (typeof text !== "string") return {};
  return Object.fromEntries(
    text
      .split("\n")
      .map((l) => l.match(/^(Q\d+):\s*(.+)$/))
      .filter((m): m is RegExpMatchArray => m !== null)
      .map((m) => [m[1], m[2].trim()]),
  );
}

// What the developer should do next, shown right above the input (like an approval prompt in a coding agent).
function NextStep(p: {
  state: PhaseState;
  all: PhaseState[];
  info: PhaseInfo;
  check?: DesignCheck | null;
  busy: boolean;
  asking: boolean; // the developer pressed Request changes and should now type below
  onRerun: (action: string) => void;
  onApprove: () => void;
  onReopen: () => void;
  onNext: (id: string) => void;
  onRequestChanges: () => void;
  runIt?: { primary: boolean; onClick: () => void }; // the program can be started: offer the way to the commands
  probe?: { label: string; onClick: () => void }; // Testing with a green run: inject bugs before approving
}) {
  const { state } = p;
  const canApprove = (state.status === "draft" || state.status === "stale") && state.can_run;
  const next = p.all.slice(p.all.findIndex((x) => x.id === state.id) + 1).find((x) => x.can_run);
  const blocker = p.all.find((x) => state.requires.includes(x.id) && x.status !== "approved");

  if (!state.can_run) {
    return (
      <div className="next" data-status={state.status === "stale" ? "stale" : "locked"}>
        <Icon name={state.status === "stale" ? "alert" : "lock"} />
        <p>
          <strong>{state.status === "stale" ? "Update needed." : "Not yet."}</strong> {statusHint(state, p.all)}
        </p>
        {blocker && (
          <div className="next-actions">
            <button type="button" className="button button-primary" onClick={() => p.onNext(blocker.id)} disabled={p.busy}>
              Go to {blocker.title}
              <Icon name="arrowRight" size={14} />
            </button>
          </div>
        )}
      </div>
    );
  }

  if (state.status === "approved") {
    return (
      <div className="next" data-status="approved">
        <Icon name="check" />
        <p>
          <strong>{p.info.title} approved.</strong>{" "}
          {p.runIt?.primary ? "The program is ready to run." : next ? `Next: ${next.title}.` : "Later phases build on it."}
        </p>
        <div className="next-actions">
          <button type="button" className="button button-quiet" onClick={p.onReopen} disabled={p.busy}>
            Reopen
          </button>
          {next && (
            <button type="button" className={p.runIt?.primary ? "button" : "button button-primary"} onClick={() => p.onNext(next.id)} disabled={p.busy}>
              Go to {next.title}
              <Icon name="arrowRight" size={14} />
            </button>
          )}
          {p.runIt && (
            <button type="button" className={p.runIt.primary ? "button button-primary" : "button"} onClick={p.runIt.onClick} disabled={p.busy}>
              Run it
            </button>
          )}
        </div>
      </div>
    );
  }
  if (state.status === "draft" || state.status === "stale") {
    // Out-of-date code that still matches the design needs no new code: say so instead of "if it still fits".
    const check = p.check?.checked ? p.check : null;
    const fits = state.status === "stale" && check?.in_sync === true;
    const drifts = check?.in_sync === false;
    const cause = state.stale_cause ? (p.all.find((x) => x.id === state.stale_cause)?.title ?? "An earlier step") : "An earlier step";
    const rerun = rerunAction(p.info);
    let text = state.status === "stale" ? statusHint(state, p.all) : "Check the results. Approve them, or ask for changes.";
    if (state.status === "stale" && rerun)
      text = `${cause} changed since this was made. ${rerun.label} to see whether it still holds, then approve; or ask for changes.`;
    if (fits) text = `${cause} changed since this was made, but the code still matches the class diagram "${check?.diagram}". Approve it again.`;
    else if (drifts)
      text = `${state.status === "stale" ? `${cause} changed since this was made. ` : ""}The code does not match the class diagram "${check?.diagram}": ${(check?.lines ?? []).join(" ")} Ask for changes, or approve if that is what you want.`;
    if (p.asking) text = "Write below what should change, then send.";
    const rerunFirst = state.status === "stale" && !!rerun && !fits && !drifts;
    const rerunPrimary = rerunFirst && !p.asking;
    return (
      <div className="next" data-status={fits ? "draft" : state.status}>
        <Icon name={fits ? "check" : state.status === "stale" ? "alert" : "sparkle"} />
        <p>
          <strong>{fits ? "Still fits." : state.status === "stale" ? "Update needed." : `${p.info.title} ready for review.`}</strong> {text}
          {(fits || drifts) && !p.asking && (
            <>
              {" "}
              <CheckedByCode />
            </>
          )}
        </p>
        <div className="next-actions">
          <button type="button" className={(drifts || p.asking) ? "button button-primary" : "button"} aria-pressed={p.asking} onClick={p.onRequestChanges} disabled={p.busy}>
            Request changes
          </button>
          {rerunFirst && rerun && (
            <button type="button" className={rerunPrimary ? "button button-primary" : "button"} onClick={() => p.onRerun(rerun.name)} disabled={p.busy}>
              <Icon name="refresh" size={14} />
              {rerun.label}
            </button>
          )}
          {p.probe && state.status === "draft" && !p.asking && (
            <button type="button" className="button" title="Wings changes one line of the code at a time and runs the tests against each change" onClick={p.probe.onClick} disabled={p.busy}>
              {p.probe.label}
            </button>
          )}
          <button type="button" className={drifts || rerunFirst || p.asking ? "button" : "button button-primary"} onClick={p.onApprove} disabled={!canApprove || p.busy}>
            <Icon name="check" size={14} />
            Approve
          </button>
        </div>
      </div>
    );
  }
  if (state.status === "needs_input") {
    return (
      <div className="next" data-status="needs_input">
        <Icon name="alert" />
        <p>
          <strong>Your answer is needed.</strong> Pick an option for each question above or type your own, then send.
        </p>
      </div>
    );
  }
  return null;
}

export function PhaseWorkspace(p: Props) {
  const { info, state } = p;
  const status = displayStatus(state);
  const [active, setActive] = useState(() => p.initialAction ?? preferredAction(info, state));
  const [values, setValues] = useState<Values>(() => p.initialValues ?? {});
  const isMaintenance = info.id === "maintenance";
  const openChange = isMaintenance ? (p.openChange ?? null) : null;
  // Phone layout shows one pane at a time. A change in progress lives in the results, so Maintenance opens there.
  const [pane, setPane] = useState<"chat" | "results">(openChange ? "results" : "chat");
  const [panelOpen, setPanelOpen] = useState(true); // wide layout: the results panel can be closed like a canvas
  const [focusSignal, setFocusSignal] = useState(0);
  const grid = useRef<HTMLDivElement>(null);
  const [chatWidth, setChatWidth] = useState<number | null>(storedWidth);
  const resize = (px: number | null) => {
    setChatWidth(px);
    try {
      if (px === null) localStorage.removeItem(CHAT_WIDTH);
      else localStorage.setItem(CHAT_WIDTH, String(px));
    } catch {
      /* storage can be unavailable */
    }
  };
  const pending = usePendingFiles(p.onUpload);
  const addFiles = useCallback((files: File[]) => pending.add(files), [pending.add]); // eslint-disable-line react-hooks/exhaustive-deps
  // Follow status changes (e.g. Answer while questions are open). Compare with the last status instead of
  // skipping the first run: StrictMode runs effects twice on mount, and a next step may have chosen the action.
  const lastStatus = useRef(state.status);
  useEffect(() => {
    if (lastStatus.current === state.status) return;
    lastStatus.current = state.status;
    setActive(preferredAction(info, state));
  }, [state.status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (p.focus.requirement || p.focus.artifact) {
      setPane("results");
      setPanelOpen(true);
    }
  }, [p.focus]);
  // A change was just requested: the tracker in the results is where it goes on.
  const openNumber = openChange?.number ?? null;
  const lastOpen = useRef(openNumber);
  useEffect(() => {
    if (openNumber !== null && lastOpen.current !== openNumber) {
      setPane("results");
      setPanelOpen(true);
    }
    lastOpen.current = openNumber;
  }, [openNumber]);
  const showChange = () => {
    setPane("results");
    setPanelOpen(true);
    window.setTimeout(() => document.getElementById("change-tracker")?.focus(), 0);
  };

  const answerKey = "answer.answers";
  const answers = parseAnswers(values[answerKey]);
  const agent = info.agents[0];
  const agentName = agent ? agentLabel(agent.name) : info.title;
  // "Answer" only makes sense while the agent waits for answers.
  const actions = info.actions.filter((a) => a.name !== "answer" || state.status === "needs_input");

  const pick = (questionId: string, option: string) => {
    const current = typeof values[answerKey] === "string" ? (values[answerKey] as string) : "";
    const lines = current.split("\n").filter((l) => l.trim() && !l.startsWith(`${questionId}:`));
    setActive("answer");
    setValues({ ...values, [answerKey]: [...lines, `${questionId}: ${option}`].sort().join("\n") });
  };

  const run = async (action: string, input: Record<string, unknown>, ids: string[]) => {
    const ok = await p.onRun(action, input, ids);
    if (ok) pending.clear();
    return ok;
  };
  const [asking, setAsking] = useState(false);
  // Pressing it again, sending, or a new message ends the request; the card and the input box show it while it lasts.
  useEffect(() => setAsking(false), [p.busy, p.messages.length, state.status]);
  const requestChanges = () => {
    const target = actions.find((a) => a.name === "revise") ?? actions.find((a) => a.name === "generate");
    if (target) setActive(target.name);
    setAsking((a) => !a);
    setFocusSignal((n) => n + 1);
  };
  // A next step an agent proposed: run it at once when it needs no input, else fill the composer to check and send.
  const step = (next: NextAction) => {
    if (next.phase !== info.id) return p.onStep(next);
    const fields = Object.entries(next.input);
    if (fields.length === 0) {
      setActive(next.action);
      run(next.action, {}, pending.ids);
      return;
    }
    setActive(next.action);
    setValues({ ...values, ...Object.fromEntries(fields.map(([k, v]) => [`${next.action}.${k}`, v as Values[string]])) });
    setFocusSignal((n) => n + 1);
  };
  // Maintenance, nothing asked yet: three ways in. Each picks its action; the check needs no input and runs at once.
  const startWith = (action: string) => {
    setActive(action);
    setFocusSignal((n) => n + 1);
  };
  const maintenanceStart =
    isMaintenance && state.can_run && !p.busy && actions.some((a) => a.name === "change") ? (
      <MaintenanceStart
        onChange={() => startWith("change")}
        onBug={() => startWith("change")}
        onCheck={
          actions.some((a) => a.name === "check")
            ? () => {
                setActive("check");
                run("check", {}, pending.ids);
              }
            : undefined
        }
      />
    ) : undefined;
  const tracked = isMaintenance ? (p.changes ?? []) : [];
  const latestChange = tracked[0]; // newest first
  // Maintenance carries changes, it is not a step to finish: its badge says where the change stands, or "Ready".
  const ownWord = isMaintenance && status !== "planned" ? maintenanceWord(status, openChange) : undefined;
  // One-click start for an empty conversation: an action without required input runs at once.
  // Only the phase's first action: it is the one that makes something (Start, Generate design).
  const suggestions = actions
    .slice(0, 1)
    .map((a) => ({
      label: a.label,
      onClick: () => {
        setActive(a.name);
        if ((a.input_schema.required ?? []).length === 0) run(a.name, {}, pending.ids);
        else setFocusSignal((n) => n + 1);
      },
    }));

  const live = p.artifacts.filter((a) => !a.retired);
  const one = (kind: string) => live.find((a) => a.kind === kind);
  const many = (kind: string) => live.filter((a) => a.kind === kind);
  const requirements = one("requirements");
  const diagrams = many("diagram").sort((a, b) => rank(a) - rank(b));
  const review = one("review");
  const testReport = one("test_report");
  const testStrength = one("test_strength");
  const runGuide = one("run_guide");
  // "Inject bugs" (P5 probe): needs a green run that is still current; the backend checks the same rule.
  const probeAction = info.actions.find((a) => a.name === "probe");
  const canProbe = !!probeAction && state.can_run && state.status !== "stale" && testReport?.content.green === true;
  const probe = () => run("probe", {}, pending.ids);
  const strengthCurrent = !!testStrength && p.trace?.strength !== null && testStrength.content.report_revision === testReport?.revision;
  const canRunIt = !!p.onRunIt && readyToRun(p.all) && (info.id !== "deployment" || !!runGuide);
  const deployCheck = one("deployment_check");
  const consistency = one("drift_report");
  const changes = many("change_request");
  const fileKinds = (["source_file", "test_file", "deployment_file"] as const).filter((k) => many(k).length > 0);
  const gaps = many("known_gaps").filter((a) => (a.content.gaps ?? []).length > 0);
  const known = new Set(["requirements", "diagram", "review", "test_report", "test_strength", "run_guide", "deployment_check", "drift_report", "change_request", "known_gaps", ...fileKinds]);
  const others = live.filter((a) => !known.has(a.kind));

  if (!info.implemented) {
    return (
      <section className="workspace workspace-planned" aria-labelledby="phase-title">
        <header className="phase-head">
          <h1 id="phase-title">{info.title}</h1>
          <StatusBadge status={status} />
        </header>
        <div className="planned">
          <p>{info.summary}</p>
          <p>
            This wing is planned. Its place, gates and status already work; its behaviour is described in{" "}
            <code>backend/src/wings/phases/{info.id}/README.md</code>.
          </p>
        </div>
      </section>
    );
  }

  const results = live.length + p.documents.length;
  const showPanel = results > 0 && panelOpen;

  return (
    <section className="workspace" aria-labelledby="phase-title" data-pane={pane} data-results={showPanel || undefined}>
      <DropZone enabled={state.can_run && !p.busy} onFiles={addFiles} />
      <header className="phase-head">
        <h1 id="phase-title" title={info.summary}>
          {info.title}
        </h1>
        <StatusBadge
          status={isMaintenance && (openChange || status === "draft") ? "ready" : status}
          label={ownWord === undefined ? undefined : (ownWord ?? "Ready")}
          title={openChange ? changeLine(openChange, p.all) : undefined}
        />
        {results > 0 && (
          <>
            <div className="pane-switch segmented" role="group" aria-label="Show">
              <button type="button" aria-pressed={pane === "chat"} onClick={() => setPane("chat")}>
                Chat
              </button>
              <button type="button" aria-pressed={pane === "results"} onClick={() => setPane("results")}>
                Results ({results})
              </button>
            </div>
            <button
              type="button"
              className="button button-quiet panel-toggle"
              aria-pressed={panelOpen}
              onClick={() => setPanelOpen(!panelOpen)}
              title={panelOpen ? "Hide the results panel" : "Show the results panel"}
            >
              <Icon name="panel" size={14} />
              {panelOpen ? "Hide results" : `Show results (${results})`}
            </button>
          </>
        )}
      </header>

      <div className="workspace-grid" ref={grid} style={chatWidth && showPanel ? ({ "--chat": `${chatWidth}px` } as React.CSSProperties) : undefined}>
        <section className="talk" aria-label={`Conversation with ${agentName}`}>
          <Conversation
            intro={EMPTY_OUTPUT[info.id] ?? info.summary}
            suggestions={state.can_run && !p.busy ? suggestions : []}
            messages={p.messages}
            events={p.events}
            agentName={agentName}
            busy={p.busy && !p.carry?.active}
            busySince={p.busySince}
            empty={maintenanceStart}
            trackedChanges={tracked.map((c) => c.number)}
            answers={answers}
            canAnswer={state.status === "needs_input" && state.can_run && !p.busy}
            onPick={pick}
            canStep={state.can_run && !p.busy}
            onStep={step}
            driftResolved={p.designCheck?.checked === true && p.designCheck.in_sync === true}
          />
          <div className="dock">
            {openChange ? (
              <ChangeDockNote open={openChange} nextTitle={p.all.find((x) => x.id === openChange.next_phase)?.title ?? null} onShow={showChange} />
            ) : (
              <NextStep
                state={state}
                all={p.all}
                info={info}
                check={p.designCheck}
                asking={asking}
                onRerun={(name) => run(name, {}, pending.ids)}
                busy={p.busy}
                onApprove={p.onApprove}
                onReopen={p.onReopen}
                onNext={p.onNext}
                onRequestChanges={requestChanges}
                runIt={canRunIt ? { primary: info.id === "deployment", onClick: () => p.onRunIt?.() } : undefined}
                probe={canProbe && probeAction && !strengthCurrent ? { label: probeAction.label, onClick: probe } : undefined}
              />
            )}
            {state.can_run && (
              <Composer
                actions={actions}
                active={active}
                onActive={setActive}
                values={values}
                onValues={setValues}
                onRestore={(back) => setValues((cur) => ({ ...back, ...Object.fromEntries(Object.entries(cur).filter(([, v]) => v !== "")) }))}
                disabled={p.busy}
                onRun={run}
                files={pending.files}
                onAddFiles={addFiles}
                onRemoveFile={pending.remove}
                focusSignal={focusSignal}
                attention={asking}
              />
            )}
          </div>
        </section>

        {showPanel && <Splitter container={grid} value={chatWidth} onChange={resize} />}
        {showPanel && (
          <section className="output" aria-label="Results">
            {latestChange && (
              <ChangeTracker
                change={latestChange}
                run={p.carry ?? null}
                busy={p.busy}
                onAdvance={(c, through) => p.onAdvance?.(c, through)}
                onStop={() => p.onStopCarry?.()}
                onOpenPhase={p.onNext}
                onOpenRequirement={p.onOpenRequirement}
                onOpenArtifact={p.onOpenArtifact}
              />
            )}
            {runGuide && (
              <RunGuideView
                guide={runGuide}
                folder={p.folder ?? null}
                focus={p.focus.artifact === runGuide.id ? p.focus : null}
                busy={p.busy}
                onOpenFolder={() => p.onOpenFolder?.()}
              />
            )}
            {requirements && (
              <RequirementsView
                key={`${requirements.id}-${requirements.revision}`}
                artifact={requirements}
                trace={p.trace}
                focus={p.focus.requirement ?? null}
                busy={p.busy}
                onOpenArtifact={p.onOpenArtifact}
                onOpenLens={p.onOpenLens}
                onSave={(c) => p.onSaveContent(requirements.id, c)}
              />
            )}
            {consistency && <ConsistencyView key={`${consistency.id}-${consistency.revision}`} report={consistency} busy={p.busy} onOpenRequirement={p.onOpenRequirement} />}
            {changes.length > 0 && (
              <ChangesView
                changes={changes}
                tracked={tracked}
                featured={latestChange?.number ?? null}
                busy={p.busy}
                onOpenRequirement={p.onOpenRequirement}
                onOpenArtifact={p.onOpenArtifact}
              />
            )}
            {review && (
              <ReviewView
                key={`${review.id}-${review.revision}`}
                review={review}
                canRun={state.can_run}
                busy={p.busy}
                onApply={(findings) => run("apply", { findings }, pending.ids)}
              />
            )}
            {testReport && (
              <TestReportView
                report={testReport}
                busy={p.busy}
                onOpenRequirement={p.onOpenRequirement}
                onProbe={canProbe && !testStrength ? probe : undefined}
                probeHint={
                  state.status === "approved"
                    ? "Wings changes one line of the code at a time and runs the tests against each change. Testing goes back to review and later steps become out of date."
                    : "Wings changes one line of the code at a time and runs the tests against each change. No model is asked."
                }
              />
            )}
            {testStrength && (
              <TestStrengthView
                key={`${testStrength.id}-${testStrength.revision}`}
                strength={testStrength}
                trace={p.trace}
                reportRevision={testReport?.revision ?? null}
                busy={p.busy}
                onOpenRequirement={p.onOpenRequirement}
                onProbe={canProbe ? probe : undefined}
              />
            )}
            {deployCheck && <DeploymentCheckView check={deployCheck} />}
            {diagrams.length > 0 && (
              <DesignView
                title={info.id === "refinement" ? "Refined design" : "Design"}
                projectId={p.projectId}
                diagrams={diagrams}
                trace={p.trace}
                canRender={p.canRender}
                focus={p.focus.artifact ?? null}
                busy={p.busy}
                onOpenRequirement={p.onOpenRequirement}
                onOpenTrace={p.onOpenTrace}
                onSetupDiagrams={p.onSetupDiagrams}
                onSave={p.onSaveText}
              />
            )}
            {fileKinds.map((k) => (
              <FilesView
                key={k}
                title={FILE_TITLE[k]}
                files={many(k)}
                focus={p.focus.artifact ?? null}
                busy={p.busy}
                editable={state.can_run}
                onOpenRequirement={p.onOpenRequirement}
                onSave={p.onSaveText}
              />
            ))}
            {gaps.map((a) => (
              <section key={a.id} className="gaps" aria-label={a.title}>
                <h2>{a.title}</h2>
                <ul>
                  {(a.content.gaps as Gap[]).map((g) => (
                    <li key={g.requirement}>
                      <button type="button" className="req-chip" disabled={p.busy} onClick={() => p.onOpenRequirement(g.requirement)}>
                        {g.requirement}
                      </button>{" "}
                      {g.reason}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            {others.map((a) => (
              <pre key={a.id} className="raw">
                {a.text}
              </pre>
            ))}
            {p.documents.length > 0 && (
              <section className="doc" aria-labelledby="docs-heading">
                <header className="doc-head">
                  <h2 id="docs-heading">Documents</h2>
                </header>
                <ul className="doc-files">
                  {p.documents.map((d) => (
                    <li key={d.id}>
                      <Icon name="file" />
                      <span className="doc-file-name">{d.name}</span>
                      <span className="doc-file-meta">
                        {formatSize(d.size)}, {d.chars.toLocaleString()} characters of text
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </section>
        )}
      </div>
    </section>
  );
}
