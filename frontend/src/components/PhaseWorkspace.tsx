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
  onRun: (action: string, input: Record<string, unknown>) => Promise<boolean>;
  onApprove: () => void;
  onReopen: () => void;
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
  requirements:
    "Requirements appear here once the analyst has enough to go on. Each one gets a stable ID such as REQ-001 that diagrams, code and tests refer to.",
  design: "Diagrams appear here: use cases, classes and the main sequences, each listing the requirements it covers.",
};

// The action a phase most likely needs next.
function preferredAction(info: PhaseInfo, state: PhaseState): string {
  const has = (name: string) => info.actions.some((a) => a.name === name);
  if (state.status === "needs_input" && has("answer")) return "answer";
  if ((state.status === "draft" || state.status === "approved") && has("revise")) return "revise";
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

export function PhaseWorkspace(p: Props) {
  const { info, state } = p;
  const status = displayStatus(state);
  const [active, setActive] = useState(() => preferredAction(info, state));
  const [values, setValues] = useState<Values>({});
  useEffect(() => setActive(preferredAction(info, state)), [state.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const canApprove = (state.status === "draft" || state.status === "stale") && state.can_run;
  const answerKey = "answer.answers";
  const answers = parseAnswers(values[answerKey]);
  const agent = info.agents[0];
  const agentName = agent ? capitalize(agent.name) : info.title;

  const pick = (questionId: string, option: string) => {
    const current = typeof values[answerKey] === "string" ? (values[answerKey] as string) : "";
    const lines = current.split("\n").filter((l) => l.trim() && !l.startsWith(`${questionId}:`));
    setActive("answer");
    setValues({ ...values, [answerKey]: [...lines, `${questionId}: ${option}`].sort().join("\n") });
  };

  // "Answer" only makes sense while the agent waits for answers.
  const actions = info.actions.filter((a) => a.name !== "answer" || state.status === "needs_input");

  const requirements = p.artifacts.find((a) => a.kind === "requirements");
  const diagrams = p.artifacts.filter((a) => a.kind === "diagram").sort((a, b) => rank(a) - rank(b));
  const others = p.artifacts.filter((a) => a.kind !== "requirements" && a.kind !== "diagram");

  return (
    <section className="workspace" aria-labelledby="phase-title">
      <header className="phase-head">
        <div className="phase-heading">
          <p className="phase-number">P{p.index + 1}</p>
          <h1 id="phase-title">{info.title}</h1>
          <StatusBadge status={status} />
        </div>
        <p className="phase-summary">{info.summary}</p>
        {state.implemented && (
          <div className="phase-next" data-status={status}>
            <p className="phase-hint">{statusHint(state, p.all)}</p>
            {state.status === "approved" ? (
              <button type="button" className="button" onClick={p.onReopen} disabled={p.busy}>
                <Icon name="undo" size={14} />
                Reopen for changes
              </button>
            ) : (
              <button type="button" className="button button-primary" onClick={p.onApprove} disabled={!canApprove || p.busy}>
                <Icon name="check" size={14} />
                Approve {info.title.toLowerCase()}
              </button>
            )}
          </div>
        )}
      </header>

      {!info.implemented ? (
        <div className="planned">
          <h2>Not built yet</h2>
          <p>
            This wing is registered in the pipeline, so its place, gates and status already work. Its behaviour is described in{" "}
            <code>backend/src/wings/phases/{info.id}/README.md</code>.
          </p>
        </div>
      ) : (
        <div className="workspace-grid">
          <section className="talk" aria-label="Conversation with the agent">
            <header className="pane-head">
              <h2>Conversation</h2>
              {info.agents.map((a) => (
                <p key={a.name} className="agent" title={a.role}>
                  {capitalize(a.name)} <span>{a.tier} model</span>
                </p>
              ))}
            </header>
            <Conversation
              messages={p.messages}
              events={p.events}
              agentName={agentName}
              busy={p.busy}
              answers={answers}
              canAnswer={state.status === "needs_input" && state.can_run && !p.busy}
              onPick={pick}
            />
            {state.can_run ? (
              <Composer
                actions={actions}
                active={active}
                onActive={setActive}
                values={values}
                onValues={setValues}
                disabled={p.busy}
                onRun={p.onRun}
              />
            ) : (
              <p className="locked-note">
                <Icon name="lock" size={14} />
                {statusHint(state, p.all)}
              </p>
            )}
          </section>
          <section className="output" aria-label="Results">
            {p.artifacts.length === 0 && (
              <div className="output-empty">
                <p>{EMPTY_OUTPUT[info.id] ?? "Results of this phase appear here."}</p>
              </div>
            )}
            {requirements && (
              <RequirementsView
                key={`${requirements.id}-${requirements.revision}`}
                artifact={requirements}
                trace={p.trace}
                focus={p.focus.requirement ?? null}
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
        </div>
      )}
    </section>
  );
}
