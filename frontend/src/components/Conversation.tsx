import { useEffect, useRef, useState } from "react";
import { SentChips } from "./FileChips";
import { Loop } from "./HowItWorks";
import type { ActivityEvent, Message, Question } from "../api/types";
import { clock } from "../lib/format";
import { eventLabel } from "../lib/status";
import { Icon } from "./Icon";

export interface Suggestion {
  label: string;
  onClick: () => void;
}

interface Props {
  intro: string; // what this phase produces, shown before anything happened
  suggestions?: Suggestion[]; // one-click starts in an empty conversation
  messages: Message[];
  events: ActivityEvent[]; // this phase's events, shown between the messages as quiet system lines
  agentName: string;
  busy: boolean;
  answers: Record<string, string>; // question id -> chosen option
  canAnswer: boolean;
  onPick: (questionId: string, option: string) => void;
}

// System steps worth a line in the conversation; the full log is in the Activity view.
const INLINE = new Set([
  "action.started",
  "agent.llm_call",
  "artifact.saved",
  "phase.stale",
  "phase.approved",
  "phase.reopened",
  "phase.error",
]);
// Steps that always stand on their own line because the developer must notice them.
const LOUD = new Set(["phase.stale", "phase.error"]);

type Entry =
  | { kind: "message"; at: string; message: Message; index: number }
  | { kind: "loud"; at: string; event: ActivityEvent }
  | { kind: "steps"; at: string; events: ActivityEvent[] };

// One short line for a run of quiet steps, e.g. "Architect replied, 3 results saved".
export function stepsSummary(events: ActivityEvent[]): string {
  const parts: string[] = [];
  const replied = events.find((e) => e.kind === "agent.llm_call");
  if (replied) parts.push(replied.summary.replace(/\s*\(.*\)$/, ""));
  const saved = events.filter((e) => e.kind === "artifact.saved").length;
  if (saved) parts.push(saved === 1 ? "1 result saved" : `${saved} results saved`);
  const approved = events.find((e) => e.kind === "phase.approved" || e.kind === "phase.reopened");
  if (approved) parts.push(approved.summary);
  return parts.length ? parts.join(", ") : `${events.length} system ${events.length === 1 ? "step" : "steps"}`;
}

function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text
        .split(/\n{2,}/)
        .filter((p) => p.trim())
        .map((p, i) => (
          <p key={i}>
            {p.split("\n").map((line, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {line}
              </span>
            ))}
          </p>
        ))}
    </>
  );
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
        <span>{stepsSummary(events)}</span>
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
function Progress({ events, agentName }: { events: ActivityEvent[]; agentName: string }) {
  const startedAt = events.map((e) => e.kind).lastIndexOf("action.started");
  const steps = startedAt < 0 ? [] : events.slice(startedAt + 1).filter((e) => e.kind === "agent.llm_call" || e.kind === "artifact.saved");
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
        </li>
      </ol>
    </li>
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

export function Conversation({ intro, suggestions = [], messages, events, agentName, busy, answers, canAnswer, onPick }: Props) {
  // Scroll only the list; scrollIntoView would also scroll the page. Stick to the bottom unless the reader scrolled up.
  const list = useRef<HTMLOListElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  const shown = events.filter((e) => INLINE.has(e.kind));
  const toBottom = () => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  };
  useEffect(() => {
    if (atBottom) toBottom();
  }, [messages.length, shown.length, busy, events.length]); // eslint-disable-line react-hooks/exhaustive-deps

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

  if (entries.length === 0 && !busy) {
    return (
      <div className="conversation-empty">
        <p>Start with the {agentName.toLowerCase()} below.</p>
        <p>{intro}</p>
        <Loop />
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
          const questions = m.data.questions ?? [];
          const mine = m.role === "developer";
          return (
            <li key={`m${entry.index}`} className="msg" data-role={m.role} data-last={entry.index === lastAgent || undefined}>
              {!mine && (
                <div className="msg-head">
                  <span className="msg-who">{agentName}</span>
                </div>
              )}
              {mine && m.data.attachments?.length ? <SentChips refs={m.data.attachments} /> : null}
              <div className="msg-body" title={clock(m.created_at)}>
                {questions.length > 0 ? (
                  <>
                    {m.data.summary && <Paragraphs text={m.data.summary} />}
                    <p className="msg-lead">Before I write anything I need to know:</p>
                    <Questions
                      questions={questions}
                      answers={answers}
                      active={canAnswer && entry.index === lastQuestions}
                      onPick={onPick}
                    />
                  </>
                ) : (
                  <Paragraphs text={m.text} />
                )}
              </div>
              {!mine && questions.length === 0 && (
                <div className="msg-actions">
                  <CopyButton text={m.text} />
                </div>
              )}
            </li>
          );
        })}
        {busy && <Progress events={events} agentName={agentName} />}
      </ol>
      {!atBottom && (
        <button type="button" className="scroll-down icon-button" aria-label="Scroll to the newest message" onClick={toBottom}>
          <Icon name="arrowDown" />
        </button>
      )}
    </div>
  );
}
