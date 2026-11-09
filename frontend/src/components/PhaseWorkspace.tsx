import { useEffect, useState } from "react";
import type { ActivityEvent, Artifact, Message, PhaseInfo, PhaseState, Trace } from "../api/types";
import { capitalize } from "../lib/format";
import { displayStatus, statusHint } from "../lib/status";
import { Composer, type Values } from "./Composer";
import { Conversation } from "./Conversation";
import { DesignView } from "./DesignView";
import { Icon } from "./Icon";
import { RequirementsView } from "./RequirementsView";
import { StatusBadge } from "./StatusBadge";

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
  focus: Focus;
  initialValues?: Values; // e.g. the description of a create-and-start whose start failed
  onRun: (action: string, input: Record<string, unknown>) => Promise<boolean>;
  onApprove: () => void;
  onReopen: () => void;
  onNext: (phase: string) => void;
  onSaveContent: (artifactId: string, content: Record<string, unknown>) => Promise<void>;
  onSaveText: (artifactId: string, text: string) => Promise<void>;
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string) => void;
  onOpenTrace: () => void;
}

// Read diagrams from the outside in: goals, then structure, then behaviour, then runtime.
const DIAGRAM_ORDER = ["use_case", "class", "sequence", "activity", "state", "component", "deployment"];
const rank = (a: Artifact) => DIAGRAM_ORDER.indexOf(a.content.kind);

const EMPTY_OUTPUT: Record<string, string> = {
  requirements: "Requirements appear here. Each one gets a stable ID such as REQ-001 that diagrams, code and tests refer to.",
  design: "Diagrams appear here: use cases, classes and the main sequences, each listing the requirements it covers.",
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
          <strong>{state.status === "stale" ? "Out of date." : "Not yet."}</strong> {statusHint(state, p.all)}
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
          <strong>{state.status === "stale" ? "Out of date." : `${p.info.title} ready for review.`}</strong>{" "}
          {state.status === "stale" ? statusHint(state, p.all) : "Check the results, then approve them or ask for changes below."}
        </p>
        <div className="next-actions">
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
  const [active, setActive] = useState(() => preferredAction(info, state));
  const [values, setValues] = useState<Values>(() => p.initialValues ?? {});
  const [pane, setPane] = useState<"chat" | "results">("chat"); // phone layout shows one pane at a time
  useEffect(() => setActive(preferredAction(info, state)), [state.status]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (p.focus.requirement || p.focus.artifact) setPane("results");
  }, [p.focus]);

  const answerKey = "answer.answers";
  const answers = parseAnswers(values[answerKey]);
  const agent = info.agents[0];
  const agentName = agent ? capitalize(agent.name) : info.title;
  // "Answer" only makes sense while the agent waits for answers.
  const actions = info.actions.filter((a) => a.name !== "answer" || state.status === "needs_input");

  const pick = (questionId: string, option: string) => {
    const current = typeof values[answerKey] === "string" ? (values[answerKey] as string) : "";
    const lines = current.split("\n").filter((l) => l.trim() && !l.startsWith(`${questionId}:`));
    setActive("answer");
    setValues({ ...values, [answerKey]: [...lines, `${questionId}: ${option}`].sort().join("\n") });
  };

  const requirements = p.artifacts.find((a) => a.kind === "requirements");
  const diagrams = p.artifacts.filter((a) => a.kind === "diagram").sort((a, b) => rank(a) - rank(b));
  const others = p.artifacts.filter((a) => a.kind !== "requirements" && a.kind !== "diagram");

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

  return (
    <section className="workspace" aria-labelledby="phase-title" data-pane={pane} data-results={p.artifacts.length > 0 || undefined}>
      <header className="phase-head">
        <h1 id="phase-title" title={info.summary}>
          {info.title}
        </h1>
        <StatusBadge status={status} />
        {p.artifacts.length > 0 && (
          <div className="pane-switch segmented" role="group" aria-label="Show">
            <button type="button" aria-pressed={pane === "chat"} onClick={() => setPane("chat")}>
              Chat
            </button>
            <button type="button" aria-pressed={pane === "results"} onClick={() => setPane("results")}>
              Results ({p.artifacts.length})
            </button>
          </div>
        )}
      </header>

      <div className="workspace-grid">
        <section className="talk" aria-label={`Conversation with ${agentName}`}>
          <Conversation
            intro={EMPTY_OUTPUT[info.id] ?? info.summary}
            messages={p.messages}
            events={p.events}
            agentName={agentName}
            busy={p.busy}
            answers={answers}
            canAnswer={state.status === "needs_input" && state.can_run && !p.busy}
            onPick={pick}
          />
          <div className="dock">
            <NextStep state={state} all={p.all} info={info} busy={p.busy} onApprove={p.onApprove} onReopen={p.onReopen} onNext={p.onNext} />
            {state.can_run && (
              <Composer
                actions={actions}
                active={active}
                onActive={setActive}
                values={values}
                onValues={setValues}
                disabled={p.busy}
                onRun={p.onRun}
              />
            )}
          </div>
        </section>

        {p.artifacts.length > 0 && (
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
            {diagrams.length > 0 && (
              <DesignView
                projectId={p.projectId}
                diagrams={diagrams}
                trace={p.trace}
                canRender={p.canRender}
                focus={p.focus.artifact ?? null}
                busy={p.busy}
                onOpenRequirement={p.onOpenRequirement}
                onOpenTrace={p.onOpenTrace}
                onSave={p.onSaveText}
              />
            )}
            {others.map((a) => (
              <pre key={a.id} className="raw">
                {a.text}
              </pre>
            ))}
          </section>
        )}
      </div>
    </section>
  );
}
