import { useCallback, useEffect, useRef, useState } from "react";
import type { ActivityEvent, Artifact, Attachment, Gap, Message, NextAction, PhaseInfo, PhaseState, Trace } from "../api/types";
import { formatSize, usePendingFiles } from "../lib/attachments";
import { agentLabel } from "../lib/format";
import { displayStatus, statusHint } from "../lib/status";
import { Composer, type Values } from "./Composer";
import { Conversation } from "./Conversation";
import { DeploymentCheckView } from "./DeploymentCheckView";
import { DesignView } from "./DesignView";
import { DropZone } from "./DropZone";
import { FilesView } from "./FilesView";
import { Icon } from "./Icon";
import { ChangesView, ConsistencyView } from "./MaintenanceViews";
import { RequirementsView } from "./RequirementsView";
import { ReviewView } from "./ReviewView";
import { Splitter } from "./Splitter";
import { StatusBadge } from "./StatusBadge";
import { TestReportView } from "./TestReportView";

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
  onOpenArtifact: (artifactId: string) => void;
  onOpenTrace: () => void;
  onSetupDiagrams: () => void; // open Settings when pictures are not set up
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

const EMPTY_OUTPUT: Record<string, string> = {
  requirements: "Requirements appear here. Each one gets a stable ID such as REQ-001 that diagrams, code and tests refer to.",
  design: "Diagrams appear here: use cases, classes and the main sequences, each listing the requirements it covers.",
  refinement: "A reviewer checks the design and lists findings. Pick the ones to apply; every diagram is updated consistently.",
  codegen: "The code appears here, file by file, written from the approved design and compared with the class diagram.",
  testing: "Tests tagged with requirement IDs appear here. Run them for real; the results show which requirements are verified.",
  deployment: "A Dockerfile, start scripts and run notes appear here, checked by code and started once for real.",
  maintenance: "Describe a change or a bug. You see what it touches and where it starts. Check consistency any time.",
};

const FILE_TITLE = { source_file: "Code", test_file: "Tests", deployment_file: "Deployment files" };

const FILE_SUMMARY: Record<string, string> = {
  source_file: "Written from the approved design. Edit a file by hand; the consistency check in Maintenance notices it.",
  test_file: "One test per acceptance criterion, named after its requirement (test_req_001_...), so results link to the trace.",
  deployment_file: "Build and start the program outside this tool. The check above proves that the files fit the code.",
};

// The action a phase most likely needs next.
function preferredAction(info: PhaseInfo, state: PhaseState): string {
  const has = (name: string) => info.actions.some((a) => a.name === name);
  if (state.status === "needs_input" && has("answer")) return "answer";
  if ((state.status === "draft" || state.status === "approved" || state.status === "stale") && has("revise")) return "revise";
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
  busy: boolean;
  onApprove: () => void;
  onReopen: () => void;
  onNext: (id: string) => void;
  onRequestChanges: () => void;
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
          <strong>{p.info.title} approved.</strong> {next ? `Next: ${next.title}.` : "Later phases build on it."}
        </p>
        <div className="next-actions">
          <button type="button" className="button button-quiet" onClick={p.onReopen} disabled={p.busy}>
            Reopen
          </button>
          {next && (
            <button type="button" className="button button-primary" onClick={() => p.onNext(next.id)} disabled={p.busy}>
              Go to {next.title}
              <Icon name="arrowRight" size={14} />
            </button>
          )}
        </div>
      </div>
    );
  }
  if (state.status === "draft" || state.status === "stale") {
    return (
      <div className="next" data-status={state.status}>
        <Icon name={state.status === "stale" ? "alert" : "sparkle"} />
        <p>
          <strong>{state.status === "stale" ? "Update needed." : `${p.info.title} ready for review.`}</strong>{" "}
          {state.status === "stale" ? statusHint(state, p.all) : "Check the results. Approve them, or ask for changes."}
        </p>
        <div className="next-actions">
          <button type="button" className="button" onClick={p.onRequestChanges} disabled={p.busy}>
            Request changes
          </button>
          <button type="button" className="button button-primary" onClick={p.onApprove} disabled={!canApprove || p.busy}>
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
  const [pane, setPane] = useState<"chat" | "results">("chat"); // phone layout shows one pane at a time
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
  const requestChanges = () => {
    if (actions.some((a) => a.name === "revise")) setActive("revise");
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
  const deployCheck = one("deployment_check");
  const consistency = one("drift_report");
  const changes = many("change_request");
  const fileKinds = (["source_file", "test_file", "deployment_file"] as const).filter((k) => many(k).length > 0);
  const gaps = many("known_gaps").filter((a) => (a.content.gaps ?? []).length > 0);
  const known = new Set(["requirements", "diagram", "review", "test_report", "deployment_check", "drift_report", "change_request", "known_gaps", ...fileKinds]);
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
        <StatusBadge status={status} />
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
            busy={p.busy}
            busySince={p.busySince}
            answers={answers}
            canAnswer={state.status === "needs_input" && state.can_run && !p.busy}
            onPick={pick}
            canStep={state.can_run && !p.busy}
            onStep={step}
          />
          <div className="dock">
            <NextStep
              state={state}
              all={p.all}
              info={info}
              busy={p.busy}
              onApprove={p.onApprove}
              onReopen={p.onReopen}
              onNext={p.onNext}
              onRequestChanges={requestChanges}
            />
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
              />
            )}
          </div>
        </section>

        {showPanel && <Splitter container={grid} value={chatWidth} onChange={resize} />}
        {showPanel && (
          <section className="output" aria-label="Results">
            {requirements && (
              <RequirementsView
                key={`${requirements.id}-${requirements.revision}`}
                artifact={requirements}
                trace={p.trace}
                focus={p.focus.requirement ?? null}
                busy={p.busy}
                onOpenArtifact={p.onOpenArtifact}
                onSave={(c) => p.onSaveContent(requirements.id, c)}
              />
            )}
            {consistency && <ConsistencyView key={`${consistency.id}-${consistency.revision}`} report={consistency} busy={p.busy} onOpenRequirement={p.onOpenRequirement} />}
            {changes.length > 0 && <ChangesView changes={changes} busy={p.busy} onOpenRequirement={p.onOpenRequirement} onOpenArtifact={p.onOpenArtifact} />}
            {review && (
              <ReviewView
                key={`${review.id}-${review.revision}`}
                review={review}
                canRun={state.can_run}
                busy={p.busy}
                onApply={(findings) => run("apply", { findings }, pending.ids)}
              />
            )}
            {testReport && <TestReportView report={testReport} busy={p.busy} onOpenRequirement={p.onOpenRequirement} />}
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
                summary={FILE_SUMMARY[k]}
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
                <p className="doc-summary">What you attached. The agents read the text of every document you attach to a message.</p>
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
