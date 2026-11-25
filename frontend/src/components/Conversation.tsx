import { useEffect, useRef, useState } from "react";
import { SentChips } from "./FileChips";
import { CheckedByCode, speakerParts } from "./CheckedByCode";
import type { ActivityEvent, Message, NextAction, Question } from "../api/types";
import { changeReplyText } from "../lib/changes";
import { answersWithQuestions, behalfLabel, byWings, isDecision, type Answered } from "../lib/history";
import type { Outgoing } from "../lib/outbox";
import { agentLabel, clock } from "../lib/format";
import { withoutLines } from "../lib/reply";
import { eventLabel } from "../lib/status";
import { Icon } from "./Icon";
import { DriftList, Reply } from "./Reply";
import { RichText } from "./RichText";

export interface Suggestion {
  label: string;
  onClick: () => void;
}

interface Props {
  intro: string; // one line: what this step does, shown before anything happened
  suggestions?: Suggestion[]; // one-click starts in an empty conversation
  messages: Message[];
  events: ActivityEvent[]; // this phase's events, shown between the messages as quiet system lines
  agentName: string;
  busy: boolean;
  busySince?: string | null;
  answers: Record<string, string>; // question id -> chosen option
  canAnswer: boolean;
  onPick: (questionId: string, option: string) => void;
  canStep?: boolean; // next steps proposed by the agent can be started
  onStep?: (step: NextAction) => void;
  driftResolved?: boolean; // design and code agree now: a message's repair steps for an old drift are moot
  empty?: React.ReactNode; // replaces the one line and its start button in an empty conversation
  trackedChanges?: number[]; // changes the tracker shows: their answers are shortened and their buttons quiet
  pending?: Outgoing[]; // sent, not saved yet (lib/outbox.ts): shown at once, "Not sent" when the run failed
  canRetry?: boolean;
  onRetry?: (o: Outgoing) => void;
}

// System steps worth a line in the conversation; the full log is in the Activity view.
const INLINE = new Set([
  "action.started",
  "agent.tool_call",
  "agent.llm_call",
  "artifact.saved",
  "phase.stale",
  "phase.approved",
  "phase.reopened",
  "phase.error",
]);
// Steps that stand on their own line because the developer must notice them. "Out of date" is not one of them:
// the next-step card says it once, the quiet line only keeps the record.
const LOUD = new Set(["phase.error"]);

type Entry =
  | { kind: "message"; at: string; message: Message; index: number }
  | { kind: "loud"; at: string; event: ActivityEvent }
  | { kind: "steps"; at: string; events: ActivityEvent[] };

// One short line for a run of quiet steps, e.g. "Architect replied, 3 results saved".
export function stepsSummary(events: ActivityEvent[]): string {
  const parts: string[] = [];
  const tools = events.filter((e) => e.kind === "agent.tool_call");
  if (tools.length) {
    const agent = agentLabel(String(tools[0].data.agent ?? "Agent"));
    parts.push(`${agent} ran ${tools.length === 1 ? "1 check" : `${tools.length} checks`}`);
  }
  const replied = events.find((e) => e.kind === "agent.llm_call");
  if (replied) parts.push(replied.summary.replace(/\s*\(.*\)$/, ""));
  const saved = events.filter((e) => e.kind === "artifact.saved").length;
  if (saved) parts.push(saved === 1 ? "1 result saved" : `${saved} results saved`);
  const approved = events.find((e) => e.kind === "phase.approved" || e.kind === "phase.reopened");
  if (approved) parts.push(approved.summary);
  return parts.length ? parts.join(", ") : `${events.length} system ${events.length === 1 ? "step" : "steps"}`;
}

function Questions(p: { questions: Question[]; answers: Record<string, string>; active: boolean; onPick: Props["onPick"] }) {
  return (
    <ol className="questions">
      {p.questions.map((q) => (
        <li key={q.id} className="question">
          <p className="question-text">{q.question}</p>
          {q.why && <p className="question-why">{q.why}</p>}
          {q.options.length > 0 && (
            <div className="options" role="group" aria-label={`Answers to ${q.id}`}>
              {q.options.map((o) => (
                <button
                  key={o}
                  type="button"
                  className="option"
                  aria-pressed={p.answers[q.id] === o}
                  disabled={!p.active}
                  onClick={() => p.onPick(q.id, o)}
                >
                  {o}
                </button>
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

function Steps({ events }: { events: ActivityEvent[] }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="steps">
      <button type="button" className="steps-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="sysline-dot" aria-hidden="true" />
        <span title={stepsSummary(events)}>Details</span>
        <Icon name="chevron" size={12} className={open ? "chevron-open" : undefined} />
      </button>
      {open && (
        <ol className="steps-list">
          {events.map((e) => (
            <li key={e.seq} className="sysline" data-kind={e.kind}>
              <span className="sr-only">{eventLabel(e.kind)}: </span>
              <span className="sysline-text">{e.summary}</span>
              <time dateTime={e.at}>{clock(e.at)}</time>
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}

// While an agent works: the steps it took so far as a checklist, the current one shimmering.
// Minutes and seconds since `since`, updated every second (real run s03: a seven-minute step looked frozen).
export function useElapsed(since: string | null | undefined): string | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!since) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [since]);
  if (!since) return null;
  const s = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function Progress({ events, agentName, since }: { events: ActivityEvent[]; agentName: string; since?: string | null }) {
  const elapsed = useElapsed(since);
  const startedAt = events.map((e) => e.kind).lastIndexOf("action.started");
  const steps =
    startedAt < 0 ? [] : events.slice(startedAt + 1).filter((e) => ["agent.tool_call", "agent.llm_call", "artifact.saved"].includes(e.kind));
  return (
    <li className="msg msg-working" data-role="agent" aria-live="polite">
      <div className="msg-head">
        <span className="msg-who">{agentName}</span>
      </div>
      <ol className="progress">
        {steps.map((e) => (
          <li key={e.seq} className="progress-done">
            <Icon name="check" size={14} />
            {e.summary.replace(/\s*\(.*\)$/, "")}
          </li>
        ))}
        <li className="progress-now">
          <Icon name="spinner" size={14} className="spin" />
          <span className="shimmer">{steps.length ? "Finishing" : "Thinking"}</span>
          {elapsed && (
            <span className="progress-time" title="Real models can take several minutes for code and tests">
              {elapsed}
            </span>
          )}
        </li>
      </ol>
    </li>
  );
}

// A decision: the developer's on the right as one line, Wings' (on the developer's behalf) on the left under its name.
// Never a bubble: a bubble holds words someone typed (ADR 0022).
function Decision({ m }: { m: Message }) {
  const wings = byWings(m);
  const action = m.data.decision?.action ?? "";
  return (
    <li className="msg msg-decision" data-role={wings ? "wings" : "developer"} data-action={action} title={clock(m.created_at)}>
      <p className="decision-line">
        <Icon name={action === "approve" ? "check" : action === "edit" ? "pencil" : action === "import" || action === "restore" ? "folder" : "arrowRight"} size={14} />
        {wings && <span className="decision-who">{behalfLabel(m.data.on_behalf)}:</span>}
        <span className="decision-text">{m.text}</span>
      </p>
      {m.data.note && (
        <p className="decision-note">
          <span className="decision-who">Wings:</span> {m.data.note}
        </p>
      )}
    </li>
  );
}

// Words Wings wrote to the agent on the developer's behalf (a redo, a change carried through): named as Wings',
// the words folded, so they never read as the developer's.
function Instruction({ m, agentName }: { m: Message; agentName: string }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="msg msg-behalf" data-role="wings" title={clock(m.created_at)}>
      <div className="msg-head">
        <span className="msg-who">{behalfLabel(m.data.on_behalf)}</span>
      </div>
      <button type="button" className="steps-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span>
          {String(m.data.label ?? "Update")}: Wings' instruction to {agentName}
        </span>
        <Icon name="chevron" size={12} className={open ? "chevron-open" : undefined} />
      </button>
      {open && (
        <div className="behalf-text">
          <RichText text={m.text} />
        </div>
      )}
    </li>
  );
}

// The developer's answers, each under the question it answers (the question card above may be long gone by then).
function Answers({ items }: { items: Answered[] }) {
  return (
    <dl className="answers">
      {items.map((a) => (
        <div key={a.id} className="answer">
          <dt>{a.question}</dt>
          <dd>{a.answer}</dd>
        </div>
      ))}
    </dl>
  );
}

// A message no agent wrote (folder sync): its name, and the label instead of the words in the name.
function Speaker({ speaker }: { speaker: string }) {
  const { name, byCode } = speakerParts(speaker);
  return (
    <>
      <span className="msg-who">{name}</span>
      {byCode && <CheckedByCode />}
    </>
  );
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="icon-button icon-button-sm"
      aria-label={done ? "Copied" : "Copy"}
      title={done ? "Copied" : "Copy"}
      onClick={() =>
        navigator.clipboard?.writeText(text).then(() => {
          setDone(true);
          window.setTimeout(() => setDone(false), 1500);
        })
      }
    >
      <Icon name={done ? "check" : "copy"} size={14} />
    </button>
  );
}

export function Conversation({
  intro,
  suggestions = [],
  messages,
  events,
  agentName,
  busy,
  busySince,
  answers,
  canAnswer,
  onPick,
  canStep = false,
  onStep,
  driftResolved = false,
  empty,
  trackedChanges = [],
  pending = [],
  canRetry = false,
  onRetry,
}: Props) {
  // Scroll only the list; scrollIntoView would also scroll the page. Stick to the bottom unless the reader scrolled up.
  const list = useRef<HTMLOListElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  const shown = events.filter((e) => INLINE.has(e.kind));
  const toBottom = () => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  };
  useEffect(() => {
    if (atBottom) toBottom();
  }, [messages.length, shown.length, busy, events.length, pending.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const lastQuestions = messages.reduce((last, m, i) => (m.data.questions?.length ? i : last), -1);
  const lastAgent = messages.reduce((last, m, i) => (m.role === "agent" ? i : last), -1);
  const timeline = [
    ...messages.map((message, index) => ({ at: message.created_at, message, index })),
    ...shown.map((event) => ({ at: event.at, event })),
  ].sort((a, b) => a.at.localeCompare(b.at));

  // Runs of quiet steps between two messages collapse into one line.
  const entries: Entry[] = [];
  for (const item of timeline) {
    if ("message" in item) entries.push({ kind: "message", ...item });
    else if (LOUD.has(item.event.kind)) entries.push({ kind: "loud", at: item.at, event: item.event });
    else {
      const last = entries.at(-1);
      if (last?.kind === "steps") last.events.push(item.event);
      else entries.push({ kind: "steps", at: item.at, events: [item.event] });
    }
  }
  // While working, the live checklist replaces the steps of the running action.
  if (busy && entries.at(-1)?.kind === "steps") entries.pop();

  if (entries.length === 0 && pending.length === 0 && !busy) {
    if (empty) return <>{empty}</>;
    return (
      <div className="conversation-empty">
        <p>{intro}</p>
        {suggestions.length > 0 && (
          <div className="suggestions">
            {suggestions.map((sg) => (
              <button key={sg.label} type="button" className="suggestion" onClick={sg.onClick}>
                {sg.label}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="conversation-wrap">
      <ol
        className="conversation"
        ref={list}
        aria-label="Conversation"
        onScroll={(e) => {
          const el = e.currentTarget;
          setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
        }}
      >
        {entries.map((entry) => {
          if (entry.kind === "steps") return <Steps key={`s${entry.events[0].seq}`} events={entry.events} />;
          if (entry.kind === "loud") {
            const e = entry.event;
            return (
              <li key={`e${e.seq}`} className="sysline sysline-loud" data-kind={e.kind}>
                <Icon name="alert" size={14} />
                <span className="sr-only">{eventLabel(e.kind)}: </span>
                <span className="sysline-text">{e.summary}</span>
              </li>
            );
          }
          const m = entry.message;
          if (isDecision(m)) return <Decision key={`m${entry.index}`} m={m} />;
          if (byWings(m)) return <Instruction key={`m${entry.index}`} m={m} agentName={agentName} />;
          const questions = m.data.questions ?? [];
          const mine = m.role === "developer";
          const answered = mine ? answersWithQuestions(messages, entry.index) : null;
          // The answer that created a tracked change: the tracker in the results panel carries it from here.
          const tracked = !mine && typeof m.data.change === "number" && trackedChanges.includes(m.data.change);
          return (
            <li key={`m${entry.index}`} className="msg" data-role={m.role} data-last={entry.index === lastAgent || undefined}>
              {!mine && (
                <div className="msg-head">
                  {m.data.speaker ? <Speaker speaker={m.data.speaker} /> : <span className="msg-who">{agentName}</span>}
                </div>
              )}
              {mine && m.data.attachments?.length ? <SentChips refs={m.data.attachments} /> : null}
              <div className="msg-body" title={clock(m.created_at)}>
                {questions.length > 0 ? (
                  <>
                    {m.data.summary && <RichText text={m.data.summary} />}
                    <Questions
                      questions={questions}
                      answers={answers}
                      active={canAnswer && entry.index === lastQuestions}
                      onPick={onPick}
                    />
                  </>
                ) : answered ? (
                  <Answers items={answered} />
                ) : mine ? (
                  <RichText text={m.text} />
                ) : (
                  <>
                    <Reply text={withoutLines(tracked ? changeReplyText(m.text) : m.text, m.data.drift ?? [])} />
                    {(m.data.drift ?? []).length > 0 && <DriftList lines={m.data.drift ?? []} />}
                  </>
                )}
              </div>
              {!mine && (m.data.drift ?? []).length > 0 && driftResolved && (
                <p className="msg-resolved" role="status">
                  <Icon name="check" size={14} /> Resolved since: design and code agree now. <CheckedByCode />
                </p>
              )}
              {!mine && !tracked && entry.index === lastAgent && (m.data.next_actions ?? []).length > 0 && onStep && !((m.data.drift ?? []).length > 0 && driftResolved) && (
                <div className="msg-next" role="group" aria-label="Next steps">
                  {(m.data.next_actions ?? []).map((s) => (
                    <button
                      key={s.label}
                      type="button"
                      className="button"
                      disabled={!canStep}
                      onClick={() => onStep(s)}
                    >
                      {s.label}
                      <Icon name="arrowRight" size={14} />
                    </button>
                  ))}
                </div>
              )}
              {!mine && questions.length === 0 && (
                <div className="msg-actions">
                  <CopyButton text={m.text} />
                </div>
              )}
            </li>
          );
        })}
        {pending.map((o) => (
          <li key={`o${o.id}`} className="msg" data-role="developer" data-state={o.state}>
            {o.message.data.attachments?.length ? <SentChips refs={o.message.data.attachments} /> : null}
            <div className="msg-body">
              <RichText text={o.message.text} />
            </div>
            {o.state === "failed" && (
              <p className="msg-unsent" role="status">
                <Icon name="alert" size={14} />
                <span>Not sent</span>
                {onRetry && (
                  <button type="button" className="button-link" disabled={!canRetry} onClick={() => onRetry(o)}>
                    Try again
                  </button>
                )}
              </p>
            )}
          </li>
        ))}
        {busy && <Progress events={events} agentName={agentName} since={busySince} />}
      </ol>
      {!atBottom && (
        <button type="button" className="scroll-down icon-button" aria-label="Scroll to the newest message" onClick={toBottom}>
          <Icon name="arrowDown" />
        </button>
      )}
    </div>
  );
}
