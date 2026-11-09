import type { Artifact, Coverage, Message, PhaseInfo, PhaseState } from "../api/types";
import { STATUS_LABEL, statusHint } from "../lib/status";
import { ActionComposer } from "./ActionComposer";
import { Conversation } from "./Conversation";
import { CoverageBar } from "./CoverageBar";
import { DiagramView } from "./DiagramView";
import { RequirementsView } from "./RequirementsView";

interface Props {
  projectId: string;
  index: number;
  info: PhaseInfo;
  state: PhaseState;
  all: PhaseState[];
  messages: Message[];
  artifacts: Artifact[];
  coverage: Coverage | null;
  canRender: boolean;
  busy: boolean;
  onRun: (action: string, input: Record<string, unknown>) => Promise<boolean>;
  onApprove: () => void;
  onReopen: () => void;
  onSaveContent: (artifactId: string, content: Record<string, unknown>) => Promise<void>;
  onSaveText: (artifactId: string, text: string) => Promise<void>;
}

// Read diagrams from the outside in: goals, then structure, then behaviour, then runtime.
const DIAGRAM_ORDER = ["use_case", "class", "sequence", "activity", "state", "component", "deployment"];
const rank = (a: Artifact) => (a.kind === "diagram" ? 1 + DIAGRAM_ORDER.indexOf(a.content.kind) : 0);

export function PhaseWorkspace(p: Props) {
  const { info, state } = p;
  const artifacts = [...p.artifacts].sort((a, b) => rank(a) - rank(b));
  const lastAgent = [...p.messages].reverse().find((m) => m.role === "agent");
  const questions = state.status === "needs_input" ? lastAgent?.data.questions ?? [] : [];
  const canApprove = (state.status === "draft" || state.status === "stale") && state.can_run;

  return (
    <section className="workspace" aria-labelledby="phase-title">
      <header className="phase-head" data-status={state.status}>
        <div>
          <p className="phase-kicker">
            P{p.index + 1} {state.implemented ? STATUS_LABEL[state.status] : "Planned"}
          </p>
          <h1 id="phase-title">{info.title}</h1>
          <p className="phase-summary">{info.summary}</p>
          <p className="phase-hint">{statusHint(state, p.all)}</p>
        </div>
        <div className="phase-controls">
          {state.status === "approved" ? (
            <button type="button" onClick={p.onReopen} disabled={p.busy}>
              Reopen for changes
            </button>
          ) : (
            <button type="button" className="approve" onClick={p.onApprove} disabled={!canApprove || p.busy}>
              Approve {info.title.toLowerCase()}
            </button>
          )}
          {info.agents.length > 0 && (
            <p className="agents">
              {info.agents.map((a) => (
                <span key={a.name}>
                  {a.name} agent, {a.tier} model
                </span>
              ))}
            </p>
          )}
        </div>
      </header>

      {!info.implemented ? (
        <div className="planned">
          <p>This wing is registered in the pipeline but not built yet. Its plan is in the backend package for this phase.</p>
        </div>
      ) : (
        <div className="workspace-grid">
          <div className="talk">
            <Conversation messages={p.messages} busy={p.busy} />
            {state.can_run ? (
              <ActionComposer actions={info.actions} questions={questions} disabled={p.busy} onRun={p.onRun} />
            ) : (
              <p className="notice">{statusHint(state, p.all)}</p>
            )}
          </div>
          <div className="artifacts">
            {artifacts.length === 0 && <p className="empty">Results of this phase will appear here.</p>}
            {info.id === "design" && p.coverage && artifacts.length > 0 && <CoverageBar coverage={p.coverage} />}
            {artifacts.map((a) =>
              a.kind === "requirements" ? (
                <RequirementsView key={`${a.id}-${a.revision}`} artifact={a} onSave={(c) => p.onSaveContent(a.id, c)} />
              ) : a.kind === "diagram" ? (
                <DiagramView
                  key={`${a.id}-${a.revision}`}
                  projectId={p.projectId}
                  artifact={a}
                  canRender={p.canRender}
                  onSave={(t) => p.onSaveText(a.id, t)}
                />
              ) : (
                <pre key={a.id} className="raw">
                  {a.text}
                </pre>
              ),
            )}
          </div>
        </div>
      )}
    </section>
  );
}
