import { useEffect, useRef, useState } from "react";
import type { ActionInfo, ActivityEvent, Artifact, Change, DesignCheck, Message, NextAction, PhaseInfo, PhaseState, Trace } from "../api/types";
import { programState, stepTitle } from "../lib/flow";
import { agentLabel } from "../lib/format";
import { type Outgoing, withoutSent } from "../lib/outbox";
import { ChangeTracker } from "./ChangeTracker";
import { CheckedByCode } from "./CheckedByCode";
import { Composer, type Values } from "./Composer";
import { Conversation } from "./Conversation";
import { Icon } from "./Icon";
import { ConsistencyView } from "./MaintenanceViews";
import { RunGuideView } from "./RunGuideView";

interface Props {
  info: PhaseInfo; // Maintenance
  state: PhaseState;
  all: PhaseState[];
  redo: string[];
  messages: Message[];
  events: ActivityEvent[];
  artifacts: Artifact[]; // Maintenance's own: consistency report, change requests
  runGuide: Artifact | null; // from Deployment
  deployCheck: Artifact | null; // from Deployment
  trace: Trace | null;
  designCheck: DesignCheck | null;
  changes: Change[]; // tracked changes, newest first
  busy: boolean; // an agent works (here or on another step): every action waits
  busySince?: string | null;
  running?: string | null; // the step the agent works on; left out: this one
  pending?: Outgoing[]; // sent from here, not saved yet (lib/outbox.ts)
  onRetry?: (o: Outgoing) => Promise<boolean>;
  folder: string | null;
  initialValues?: Values;
  onRun: (action: string, input: Record<string, unknown>) => Promise<boolean>; // a Maintenance action
  onProbe: () => void; // Tests: inject bugs
  onGo: (phase: string) => void;
  onStep: (step: NextAction) => void;
  onOpenFolder: () => void;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase?: string) => void;
}

interface Check {
  ok: boolean | null; // null: not known yet
  text: string;
  action?: { label: string; run: () => void };
}

// After the build: how to start the program, what code checked about it, and one box for the next change.
// A change started here revises the requirements; the steps that have to follow it are then redone with the
// developer through the same loop as the build (RedoStrip, step screens).
export function ProgramView(p: Props) {
  const status = programState(p.all, p.redo);
  const here = p.busy && (p.running === undefined || p.running === "maintenance");
  const unsent = p.pending ?? [];
  const runningTitle = p.running ? stepTitle(p.all.find((x) => x.id === p.running) ?? { id: p.running }) : "the agent";
  // While the agent works here the conversation shows the sent change and the working line, as on a step.
  const [view, setView] = useState<"program" | "conversation">(here ? "conversation" : "program");
  const wasHere = useRef(here);
  useEffect(() => {
    if (wasHere.current === here) return;
    wasHere.current = here;
    setView(here || unsent.some((o) => o.state === "failed") ? "conversation" : "program");
  }, [here]); // eslint-disable-line react-hooks/exhaustive-deps
  const [values, setValues] = useState<Values>(() => p.initialValues ?? {});
  useEffect(() => {
    if (p.initialValues) setValues((cur) => ({ ...p.initialValues, ...Object.fromEntries(Object.entries(cur).filter(([, v]) => v !== "")) }));
  }, [p.initialValues]);
  const [active, setActive] = useState("change");
  const [doing, setDoing] = useState<string>("change"); // what the busy line says
  const DOING: Record<string, string> = {
    change: "Working out what the change touches",
    probe: "Injecting bugs and running the tests against each",
    check: "Comparing design, code and tests",
    discuss: "Answering",
  };
  const consistency = p.artifacts.find((a) => a.kind === "drift_report" && !a.retired) ?? null;
  const latest = p.changes[0] ?? null;
  const canChange = p.state.can_run && status.kind === "ready"; // one change at a time
  const label: Record<string, string> = { change: "Change it", discuss: "Ask a question" };
  const actions: ActionInfo[] = ["change", "discuss"]
    .map((n) => p.info.actions.find((a) => a.name === n))
    .filter((a): a is ActionInfo => !!a)
    .map((a) => ({ ...a, label: label[a.name] ?? a.label }));
  const check = p.info.actions.find((a) => a.name === "check");

  const checks: Check[] = [];
  if (p.trace && p.trace.requirements.length > 0) {
    const total = p.trace.requirements.length;
    const passed = Object.values(p.trace.results ?? {}).filter((v) => v === "passed").length;
    checks.push({ ok: passed === total, text: `${passed} of ${total} requirements have a passing test.` });
  }
  if (p.designCheck?.checked) {
    const k = p.designCheck.lines?.length ?? 0;
    checks.push({
      ok: p.designCheck.in_sync === true,
      text: p.designCheck.in_sync ? "The code matches the class diagram." : `The code differs from the class diagram in ${k} ${k === 1 ? "place" : "places"}.`,
    });
  }
  if (p.deployCheck) {
    checks.push({ ok: p.deployCheck.content.passed === true, text: p.deployCheck.content.passed ? "The program started in the deployment check." : "The deployment check failed." });
  }
  if (status.kind === "ready") {
    const s = p.trace?.strength ?? null;
    const judged = s ? s.caught + s.survived : 0;
    checks.push(
      s && judged > 0
        ? { ok: s.survived === 0, text: `The tests caught ${s.caught} of ${judged} injected bugs.`, action: { label: "Inject bugs again", run: () => { setDoing("probe"); p.onProbe(); } } }
        : { ok: null, text: "Do the tests catch bugs? Inject some and find out.", action: { label: "Inject bugs", run: () => { setDoing("probe"); p.onProbe(); } } },
    );
  }

  return (
    <section className="step-screen program" aria-labelledby="program-title" data-view={view}>
      <header className="step-head">
        <div>
          <p className="step-count">After the build</p>
          <h1 id="program-title">Your program</h1>
        </div>
        {(p.messages.length > 0 || unsent.length > 0 || here) && (
          <div className="segmented" role="group" aria-label="Show">
            <button type="button" aria-pressed={view === "program"} onClick={() => setView("program")}>
              Program
            </button>
            <button type="button" aria-pressed={view === "conversation"} onClick={() => setView("conversation")}>
              Conversation <span className="count">{p.messages.length + unsent.length}</span>
            </button>
          </div>
        )}
      </header>

      <p className="marked" data-tone={status.kind === "ready" ? "ok" : status.kind === "redo" ? "redo" : "read"}>
        <span className="marked-text">{status.text}</span>
      </p>

      <div className="step-body">
        {view === "conversation" ? (
          <Conversation
            intro=""
            suggestions={[]}
            messages={p.messages}
            events={p.events}
            agentName={p.info.agents[0] ? agentLabel(p.info.agents[0].name) : "Agent"}
            busy={here}
            busySince={p.busySince}
            trackedChanges={p.changes.map((c) => c.number)}
            pending={unsent}
            canRetry={p.state.can_run && !p.busy}
            onRetry={(o) => {
              setValues((cur) => withoutSent(cur, o.action, o.input));
              void p.onRetry?.(o);
            }}
            answers={{}}
            canAnswer={false}
            onPick={() => undefined}
            canStep={p.state.can_run && !p.busy}
            onStep={p.onStep}
          />
        ) : (
          <div className="results program-body">
            {status.step && (
              <div className="program-next">
                <button type="button" className="button button-primary button-big" onClick={() => p.onGo(status.step!)}>
                  {status.kind === "redo" ? "Go to" : "Continue with"} {stepTitle(p.all.find((x) => x.id === status.step) ?? { id: status.step })}
                  <Icon name="arrowRight" size={16} />
                </button>
              </div>
            )}

            {p.runGuide && <RunGuideView guide={p.runGuide} folder={p.folder} focus={null} onOpenFolder={p.onOpenFolder} />}

            {checks.length > 0 && (
              <section className="doc program-checks" aria-labelledby="checks-heading">
                <header className="doc-head">
                  <div>
                    <h2 id="checks-heading">What code checked</h2>
                    <p className="meta">
                      <CheckedByCode /> No model judged any of this.
                    </p>
                  </div>
                </header>
                <ul className="check-list">
                  {checks.map((c) => (
                    <li key={c.text} data-ok={c.ok === null ? undefined : String(c.ok)}>
                      <span className="check-mark" aria-hidden="true">
                        <Icon name={c.ok === null ? "help" : c.ok ? "check" : "alert"} size={14} />
                      </span>
                      <span>{c.text}</span>
                      {c.action && (
                        <button type="button" className="button" disabled={p.busy} onClick={c.action.run}>
                          {c.action.label}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
                {consistency && (
                  <details className="program-details">
                    <summary>Requirement by requirement</summary>
                    <ConsistencyView key={`${consistency.id}-${consistency.revision}`} report={consistency} onOpenRequirement={p.onOpenRequirement} />
                  </details>
                )}
                {check && canChange && (
                  <button type="button" className="button-link" disabled={p.busy} onClick={() => { setDoing("check"); void p.onRun("check", {}); }}>
                    Check consistency again
                  </button>
                )}
              </section>
            )}

            {latest && (
              <ChangeTracker
                change={latest}
                running={false}
                activePhase={null}
                onOpenPhase={p.onGo}
                onOpenRequirement={p.onOpenRequirement}
                onOpenArtifact={(id, phase) => p.onOpenArtifact(id, phase)}
              />
            )}
          </div>
        )}
      </div>

      {canChange && actions.length > 0 && (
        <footer className="action-bar program-change" data-busy={here || undefined}>
          <h2 className="change-title">What should change?</h2>
          {p.busy && !here && <p className="decide-note decide-wait">Changes wait until {runningTitle} is done.</p>}
          {here ? (
            <p className="working" role="status">
              <Icon name="spinner" className="spin" />
              <span>{DOING[doing] ?? "Working"}</span>
            </p>
          ) : (
            <Composer
              actions={actions}
              active={active}
              onActive={setActive}
              values={values}
              onValues={setValues}
              onRestore={(back) => setValues((cur) => ({ ...back, ...Object.fromEntries(Object.entries(cur).filter(([, v]) => v !== "")) }))}
              disabled={p.busy}
              working={false}
              onRun={(a, input) => {
                setDoing(a);
                if (a === "discuss") setView("conversation");
                return p.onRun(a, input);
              }}
              placeholder={active === "discuss" ? "Ask about your program" : "A new feature, a bug, a different behaviour. The steps it touches are then redone with you."}
            />
          )}
        </footer>
      )}
    </section>
  );
}
