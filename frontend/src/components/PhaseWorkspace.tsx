import { useCallback, useEffect, useRef, useState } from "react";
import type { ActionInfo, ActivityEvent, Artifact, Attachment, DesignCheck, Gap, Message, NextAction, PhaseInfo, PhaseState, Trace, Verification } from "../api/types";
import { formatSize, usePendingFiles } from "../lib/attachments";
import { type ChoiceValues, choiceDefaults, missingChoice } from "../lib/choices";
import { agentLabel } from "../lib/format";
import { byWings, isDecision, typedByDeveloper } from "../lib/history";
import { type Act, buildSteps, type Screen, screen, stepTitle } from "../lib/flow";
import { type Outgoing, withoutSent } from "../lib/outbox";
import { CheckedByCode } from "./CheckedByCode";
import { Composer, type Values } from "./Composer";
import { Conversation } from "./Conversation";
import { DeploymentCheckView } from "./DeploymentCheckView";
import { DesignView } from "./DesignView";
import { DropZone } from "./DropZone";
import { FilesView } from "./FilesView";
import { FixAttemptsView } from "./FixAttemptsView";
import { Icon } from "./Icon";
import { FoldList, Reply } from "./Reply";
import { RequirementsView } from "./RequirementsView";
import { ReviewView } from "./ReviewView";
import { RunGuideView } from "./RunGuideView";
import { StartChoices } from "./StartChoices";
import { TestReportView } from "./TestReportView";
import { TestStrengthView } from "./TestStrengthView";

export type Focus = { requirement?: string; artifact?: string };

interface Props {
  projectId: string;
  info: PhaseInfo;
  catalog: PhaseInfo[];
  state: PhaseState;
  all: PhaseState[];
  redo: string[]; // steps that have to follow a change, in order
  messages: Message[];
  events: ActivityEvent[];
  artifacts: Artifact[];
  trace: Trace | null;
  designCheck?: DesignCheck | null; // Code: the code against the current class diagram, checked by code
  canRender: boolean;
  busy: boolean; // an agent works (here or on another step): every action waits
  busySince?: string | null;
  running?: string | null; // the step the agent works on; left out: this one. Other steps are read-only meanwhile
  pending?: Outgoing[]; // this step's messages that are sent but not saved yet (lib/outbox.ts)
  onRetry?: (o: Outgoing) => Promise<boolean>; // send a message that was not sent again
  focus: Focus;
  initialValues?: Values;
  initialAction?: string;
  documents: Attachment[];
  onUpload: (file: File) => Promise<Attachment>;
  onRun: (action: string, input: Record<string, unknown>, attachments: string[]) => Promise<boolean>;
  onAccept: () => void; // approve, then the next step (lib/flow.ts afterAccept)
  onRedo: () => void; // make this step again so it follows the change; it then waits for Accept
  onKeep: () => void; // accept a step that needs a redo as it is
  onGo: (phase: string) => void;
  onStep: (step: NextAction) => void; // a next step an agent proposed for another phase
  onSaveContent: (artifactId: string, content: Record<string, unknown>) => Promise<void>;
  onSaveText: (artifactId: string, text: string) => Promise<void>;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase?: string) => void;
  onOpenTrace: () => void;
  onSetupDiagrams: () => void;
  folder?: string | null;
  onOpenFolder?: () => void;
  onOpenLens?: (requirementId: string) => void;
}

// Read diagrams from the outside in: goals, then structure, then behaviour, then runtime.
const DIAGRAM_ORDER = ["use_case", "class", "sequence", "activity", "state", "component", "deployment"];
const rank = (a: Artifact) => DIAGRAM_ORDER.indexOf(a.content.kind);

const FILE_TITLE = { source_file: "Code", test_file: "Tests", deployment_file: "Deployment files" };

/** The words in the text box: the same idea everywhere, "change this step", or a question. */
const COMPOSER_LABEL: Record<string, string> = {
  start: "Describe it",
  answer: "Answer",
  revise: "Change it",
  change: "Change it",
  discuss: "Ask a question",
  generate: "Change the tests", // Tests only: writes them again with the guidance typed here
};

/** The text box's hint for a mode that is not the step's usual "change" (the question has its own). */
const PLACEHOLDER: Record<string, string> = {
  generate: "Say what the tests should do differently",
};

/** What the working step does, in the step's own words. */
const WORKING: Record<string, string> = {
  requirements: "The analyst is writing the requirements",
  design: "The architect is drawing the design",
  refinement: "The reviewer is reading the design",
  codegen: "The coder is writing the code",
  testing: "The tester is at work",
  deployment: "Wings is preparing the deployment",
};

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

/** After a while: real model steps take minutes, so say so once instead of leaving the developer guessing. */
function SlowHint({ since }: { since?: string | null }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => tick((n) => n + 1), 5000);
    return () => window.clearInterval(id);
  }, []);
  if (!since || Date.now() - Date.parse(since) < 15000) return null;
  return <span className="slow-hint">A step usually takes one to three minutes.</span>;
}

function Elapsed({ since }: { since?: string | null }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  if (!since) return null;
  const s = Math.max(0, Math.round((now - Date.parse(since)) / 1000));
  return <span className="elapsed">{`${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`}</span>;
}

export function PhaseWorkspace(p: Props) {
  const { info, state } = p;
  const live = p.artifacts.filter((a) => !a.retired);
  const one = (kind: string) => live.find((a) => a.kind === kind);
  const testReport = one("test_report");
  const testStrength = one("test_strength");
  const deployCheck = one("deployment_check");
  const review = one("review");
  const [pickedFindings, setPickedFindings] = useState<string[]>([]);
  const lastAgent = [...p.messages].reverse().find((m) => m.role === "agent");
  const asked = state.status === "needs_input" ? (lastAgent?.data.questions?.length ?? 0) : 0;
  const strengthCurrent = !!testStrength && p.trace?.strength !== null && testStrength.content.report_revision === testReport?.revision;

  const [values, setValues] = useState<Values>(() => p.initialValues ?? {});
  // Words handed back by the app (a run that failed while this screen was closed): into empty fields only.
  useEffect(() => {
    if (p.initialValues) setValues((cur) => ({ ...p.initialValues, ...Object.fromEntries(Object.entries(cur).filter(([, v]) => v !== "")) }));
  }, [p.initialValues]);
  // A step that asks before its agent starts (Design, Tests): what is ticked, from the schema's defaults.
  const generator = info.actions[0];
  const [choice, setChoice] = useState<ChoiceValues>(() => choiceDefaults(generator));
  const s: Screen = screen({
    phase: state,
    all: p.all,
    redo: p.redo,
    catalog: p.catalog,
    hasResult: live.length > 0,
    check: info.id === "codegen" ? p.designCheck : null,
    tests: testReport ? { total: (testReport.content.tests ?? []).length || Number(testReport.content.passed ?? 0) + Number(testReport.content.failed ?? 0) + Number(testReport.content.errors ?? 0), failed: Number(testReport.content.failed ?? 0) + Number(testReport.content.errors ?? 0) } : null,
    deploy: deployCheck ? { passed: deployCheck.content.passed === true } : null,
    openFindings: review ? ((review.content.findings ?? []) as { status: string }[]).filter((f) => f.status === "open").length : 0,
    canProbe: info.id === "testing" && testReport?.content.green === true && !strengthCurrent && state.status !== "stale",
    pickedFindings: pickedFindings.length,
    answers: asked > 0 ? { picked: Object.keys(parseAnswers(values["answer.answers"])).length, asked } : undefined,
    verification: info.id === "testing" && testReport?.content.verification ? (testReport.content.verification as Verification) : null,
    strength: strengthCurrent && p.trace?.strength ? { caught: p.trace.strength.caught, judged: p.trace.strength.caught + p.trace.strength.survived } : null,
    choiceMissing: missingChoice(generator, choice) !== null,
  });

  // The agent works on this step (else, while busy, on another one and this step is read-only).
  const here = p.busy && (p.running === undefined || p.running === info.id);
  const unsent = p.pending ?? [];
  const unsentHere = unsent.some((o) => o.state === "failed");
  const runningTitle = p.running ? stepTitle(p.all.find((x) => x.id === p.running) ?? { id: p.running }) : "the agent";

  // While the agent works here the conversation shows (the sent message, the working line); afterwards the step
  // opens as it would anyway, unless a message was not sent: that one stays in view.
  const [tab, setTab] = useState<Screen["tab"]>(here ? "conversation" : s.tab);
  const lastStatus = useRef(state.status);
  useEffect(() => {
    if (lastStatus.current === state.status) return;
    lastStatus.current = state.status;
    setTab(here ? "conversation" : s.tab);
  }, [state.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const wasHere = useRef(here);
  useEffect(() => {
    if (wasHere.current === here) return;
    wasHere.current = here;
    setTab(here || unsentHere ? "conversation" : s.tab);
  }, [here]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (p.focus.requirement || p.focus.artifact) setTab("result");
  }, [p.focus]);

  const composerActions: ActionInfo[] = s.composer
    .map((n) => info.actions.find((a) => a.name === n))
    .filter((a): a is ActionInfo => !!a)
    .map((a) => ({ ...a, label: COMPOSER_LABEL[a.name] ?? a.label }));
  // The switch always shows the change first and the question last; the default (s.composer[0]) is pressed.
  const switchOrder = [...composerActions].sort((a, b) => Number(a.name === "discuss") - Number(b.name === "discuss"));
  const [active, setActive] = useState(() => p.initialAction ?? composerActions[0]?.name ?? "");
  const composerKey = useRef(s.composer.join(","));
  useEffect(() => {
    if (composerKey.current === s.composer.join(",")) return;
    composerKey.current = s.composer.join(",");
    // The state moved on (e.g. from "nothing yet" to a result): the box means "change this step" again.
    setActive(composerActions[0]?.name ?? "");
  }, [s.composer.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const [focusSignal, setFocusSignal] = useState(0);
  const [keeping, setKeeping] = useState(false);
  useEffect(() => setKeeping(false), [p.busy, state.status]);

  const pending = usePendingFiles(p.onUpload);
  const addFiles = useCallback((files: File[]) => pending.add(files), [pending.add]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (action: string, input: Record<string, unknown>, ids: string[] = pending.ids) => {
    const ok = await p.onRun(action, input, ids);
    if (ok) pending.clear();
    return ok;
  };

  // Try again sends the words from the bubble; the same words leave the box, so they are not sent twice.
  const retry = async (o: Outgoing) => {
    if (!p.onRetry) return;
    setValues((cur) => withoutSent(cur, o.action, o.input));
    await p.onRetry(o);
  };

  const answerKey = "answer.answers";
  const answers = parseAnswers(values[answerKey]);
  const pick = (questionId: string, option: string) => {
    const current = typeof values[answerKey] === "string" ? (values[answerKey] as string) : "";
    const lines = current.split("\n").filter((l) => l.trim() && !l.startsWith(`${questionId}:`));
    setActive("answer");
    setValues({ ...values, [answerKey]: [...lines, `${questionId}: ${option}`].sort().join("\n") });
  };
  const step = (next: NextAction) => {
    if (next.phase !== info.id) return p.onStep(next);
    const fields = Object.entries(next.input);
    setActive(next.action);
    if (fields.length === 0) return void run(next.action, {});
    setValues({ ...values, ...Object.fromEntries(fields.map(([k, v]) => [`${next.action}.${k}`, v as Values[string]])) });
    setFocusSignal((n) => n + 1);
  };

  const act = (a: Act) => {
    switch (a.id) {
      case "accept":
        return p.onAccept();
      case "redo":
        return p.onRedo();
      case "keep":
        return setKeeping(true);
      case "go":
        return a.phase && p.onGo(a.phase);
      case "apply":
        return void run("apply", { findings: pickedFindings });
      case "send_answers": {
        // Like the text box: the answers leave at once and come back if the run fails.
        const text = values["answer.answers"];
        setValues({ ...values, "answer.answers": "" });
        return void run("answer", { answers: text }).then((ok) => {
          if (!ok) setValues((cur) => (cur["answer.answers"] ? cur : { ...cur, "answer.answers": text }));
        });
      }
      case "fix_drift": {
        const lines = p.designCheck?.lines ?? [];
        return void run("revise", { feedback: `Change the code so it matches the class diagram${p.designCheck?.diagram ? ` "${p.designCheck.diagram}"` : ""}:\n${lines.map((l) => `- ${l}`).join("\n")}` });
      }
      case "start":
        return void (a.action && run(a.action, s.choices === a.action ? choice : {}));
      case "explain":
      case "probe":
      case "rerun":
        return void (a.action && run(a.action, {}));
    }
  };

  const steps = buildSteps(p.all);
  const number = steps.findIndex((x) => x.id === info.id) + 1;
  const agentName = info.agents[0] ? agentLabel(info.agents[0].name) : stepTitle(info);
  const results = live.length + (info.id === "requirements" ? p.documents.length : 0);
  const said = p.messages.length + unsent.length;
  const showTabs = results > 0 && (said > 0 || here);
  const view = showTabs ? tab : results > 0 ? "result" : "conversation";
  // What the agent said about this result, when it answered the developer's latest request: the answer to "change it".
  // Decision lines ("Accepted", "Run the tests") are no request to answer; Wings' instruction on the developer's behalf is.
  const talk = p.messages.filter((m) => !isDecision(m));
  const last = talk[talk.length - 1];
  const requested = talk.some((m) => typedByDeveloper(m) || byWings(m));
  const lastReply = last?.role === "agent" && requested && !last.data.questions?.length ? (last.data.summary ?? last.text) : null;

  return (
    <section className="step-screen" aria-labelledby="step-title" data-view={view}>
      <DropZone enabled={state.can_run && !p.busy} onFiles={addFiles} />
      <header className="step-head">
        <div>
          {number > 0 && (
            <p className="step-count">
              Step {number} of {steps.length}
            </p>
          )}
          <h1 id="step-title" title={info.summary}>
            {stepTitle(info)}
          </h1>
        </div>
        {showTabs && (
          <div className="segmented" role="group" aria-label="Show">
            <button type="button" aria-pressed={view === "result"} onClick={() => setTab("result")}>
              Result
            </button>
            <button type="button" aria-pressed={view === "conversation"} onClick={() => setTab("conversation")}>
              Conversation <span className="count">{said}</span>
            </button>
          </div>
        )}
      </header>

      {s.marked && !here && (
        <p className="marked" data-tone={s.marked.tone} role={s.marked.tone === "problem" || s.marked.tone === "redo" ? "status" : undefined}>
          <span className="marked-text">{s.marked.text}</span>
          {s.marked.byCode && <CheckedByCode />}
        </p>
      )}
      {s.marked?.details && s.marked.details.length > 0 && !here &&<FoldList items={s.marked.details} className="marked-details" limit={4} />}

      <div className="step-body">
        {view === "conversation" && s.choices && generator?.name === s.choices && (
          <StartChoices action={generator} values={choice} onChange={setChoice} disabled={p.busy} />
        )}
        {view === "conversation" && s.choices && said === 0 && !p.busy ? null : view === "conversation" ? (
          <Conversation
            intro=""
            suggestions={[]}
            messages={p.messages}
            events={p.events}
            agentName={agentName}
            busy={here}
            busySince={p.busySince}
            trackedChanges={[]}
            pending={unsent}
            canRetry={state.can_run && !p.busy}
            onRetry={(o) => void retry(o)}
            answers={answers}
            canAnswer={state.status === "needs_input" && state.can_run && !p.busy}
            onPick={pick}
            canStep={state.can_run && !p.busy}
            onStep={step}
            driftResolved={p.designCheck?.checked === true && p.designCheck.in_sync === true}
          />
        ) : (
          <>
            {lastReply && (
              <aside className="last-reply" aria-label={`${agentName} says`}>
                <p className="last-reply-who">
                  {agentName}
                  <button type="button" className="button-link" onClick={() => setTab("conversation")}>
                    Whole conversation
                  </button>
                </p>
                <Reply text={lastReply} />
              </aside>
            )}
            <Results {...p} live={live} run={run} onPicked={setPickedFindings} />
          </>
        )}
      </div>

      <footer className="action-bar" data-busy={here || undefined}>
        {here ? (
          <p className="working" role="status">
            <Icon name="spinner" className="spin" />
            <span>{WORKING[info.id] ?? "Wings is working"}</span>
            <Elapsed since={p.busySince} />
            <SlowHint since={p.busySince} />
          </p>
        ) : keeping ? (
          <div className="decide" role="group" aria-label="Keep this step">
            <p>
              Keep {stepTitle(info)} unchanged? Later steps may then not match it.
            </p>
            <button type="button" className="button button-primary" onClick={() => { setKeeping(false); p.onKeep(); }}>
              Yes, keep it
            </button>
            <button type="button" className="button-link" onClick={() => setKeeping(false)}>
              Cancel
            </button>
          </div>
        ) : (
          (s.primary || s.secondary.length > 0) && (
            <div className="decide">
              {p.busy ? <p className="decide-note decide-wait">Actions here wait until {runningTitle} is done.</p> : s.note && <p className="decide-note">{s.note}</p>}
              {s.secondary.map((a) => (
                <button key={a.id + a.label} type="button" className="button-link" title={a.hint} disabled={p.busy && a.id !== "go"} onClick={() => act(a)}>
                  {a.label}
                </button>
              ))}
              {s.primary && (
                <button type="button" className="button button-primary button-big" title={s.primary.hint} disabled={p.busy && s.primary.id !== "go"} onClick={() => act(s.primary!)}>
                  {s.primary.label}
                  <Icon name="arrowRight" size={16} />
                </button>
              )}
            </div>
          )
        )}
        {composerActions.length > 0 && (
          <Composer
            actions={switchOrder}
            active={active}
            onActive={setActive}
            values={values}
            onValues={setValues}
            onRestore={(back) => setValues((cur) => ({ ...back, ...Object.fromEntries(Object.entries(cur).filter(([, v]) => v !== "")) }))}
            disabled={p.busy}
            working={here}
            onRun={(a, input, ids) => {
              if (a === "discuss" || a === "answer") setTab("conversation");
              return run(a, input, ids);
            }}
            files={pending.files}
            onAddFiles={addFiles}
            onRemoveFile={pending.remove}
            focusSignal={focusSignal}
            placeholder={active === "discuss" ? "Ask the agent a question" : (PLACEHOLDER[active] ?? s.placeholder)}
          />
        )}
      </footer>
    </section>
  );
}

// What the step made, newest kind of result first. Nothing here decides the way on.
function Results(p: Props & { live: Artifact[]; run: (action: string, input: Record<string, unknown>) => Promise<boolean>; onPicked: (ids: string[]) => void }) {
  const { info, state, live } = p;
  const one = (kind: string) => live.find((a) => a.kind === kind);
  const many = (kind: string) => live.filter((a) => a.kind === kind);
  const requirements = one("requirements");
  const diagrams = many("diagram").sort((a, b) => rank(a) - rank(b));
  const review = one("review");
  const testReport = one("test_report");
  const testStrength = one("test_strength");
  const fixLog = one("fix_log");
  const runGuide = one("run_guide");
  const deployCheck = one("deployment_check");
  const fileKinds = (["source_file", "test_file", "deployment_file"] as const).filter((k) => many(k).length > 0);
  const gaps = many("known_gaps").filter((a) => (a.content.gaps ?? []).length > 0);
  const known = new Set(["requirements", "diagram", "review", "test_report", "test_strength", "fix_log", "run_guide", "deployment_check", "known_gaps", ...fileKinds]);
  const others = live.filter((a) => !known.has(a.kind));
  const probe = info.actions.some((a) => a.name === "probe") && state.can_run && state.status !== "stale" && testReport?.content.green === true ? () => p.run("probe", {}) : undefined;

  return (
    <div className="results">
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
      {review && (
        <ReviewView key={`${review.id}-${review.revision}`} review={review} canRun={state.can_run} busy={p.busy} onApply={(findings) => p.run("apply", { findings })} onPicked={p.onPicked} />
      )}
      {testReport && <TestReportView report={testReport} busy={p.busy} onOpenRequirement={p.onOpenRequirement} />}
      {fixLog && <FixAttemptsView attempts={fixLog.content.attempts ?? []} />}
      {testStrength && (
        <TestStrengthView
          key={`${testStrength.id}-${testStrength.revision}`}
          strength={testStrength}
          trace={p.trace}
          reportRevision={testReport?.revision ?? null}
          busy={p.busy}
          onOpenRequirement={p.onOpenRequirement}
          onProbe={probe}
        />
      )}
      {deployCheck && <DeploymentCheckView check={deployCheck} />}
      {runGuide && (
        <RunGuideView guide={runGuide} folder={p.folder ?? null} focus={p.focus.artifact === runGuide.id ? p.focus : null} onOpenFolder={() => p.onOpenFolder?.()} />
      )}
      {diagrams.length > 0 && (
        <DesignView
          title={info.id === "refinement" ? "Design after the review" : "Diagrams"}
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
          <p className="gaps-hint">
            This does not block you. You can accept the step as it is, or type below what the code should do instead and press Change it.
          </p>
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
      {info.id === "requirements" && p.documents.length > 0 && (
        <section className="doc" aria-labelledby="docs-heading">
          <header className="doc-head">
            <h2 id="docs-heading">Your documents</h2>
          </header>
          <ul className="doc-files">
            {p.documents.map((d) => (
              <li key={d.id}>
                <Icon name="file" />
                <span className="doc-file-name">{d.name}</span>
                <span className="doc-file-meta">{formatSize(d.size)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
