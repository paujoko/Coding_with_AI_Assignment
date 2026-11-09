import { useEffect, useRef, useState } from "react";
import type { ActivityEvent, Message, Question } from "../api/types";
import { clock } from "../lib/format";
import { eventLabel } from "../lib/status";
import { Icon } from "./Icon";

interface Props {
  intro: string; // what this phase produces, shown before anything happened
  messages: Message[];
  events: ActivityEvent[]; // this phase's events, shown between the messages as quiet system lines
  agentName: string;
  busy: boolean;
  answers: Record<string, string>; // question id -> chosen option
  canAnswer: boolean;
  onPick: (questionId: string, option: string) => void;
}

// System steps worth a line in the conversation; the full log is in the Activity view.
const INLINE = new Set(["action.started", "agent.llm_call", "artifact.saved", "phase.stale", "phase.approved", "phase.reopened", "phase.error"]);
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

export function Conversation({ intro, messages, events, agentName, busy, answers, canAnswer, onPick }: Props) {
  // Scroll only the list to its newest entry; scrollIntoView would also scroll the page.
  const list = useRef<HTMLOListElement>(null);
  const shown = events.filter((e) => INLINE.has(e.kind));
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [messages.length, shown.length, busy]);

  const lastQuestions = messages.reduce((last, m, i) => (m.data.questions?.length ? i : last), -1);
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

  if (entries.length === 0 && !busy) {
    return (
      <div className="conversation-empty">
        <p>Start with the {agentName.toLowerCase()} below.</p>
        <p>{intro}</p>
      </div>
    );
  }

  return (
    <ol className="conversation" ref={list} aria-label="Conversation">
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
          <li key={`m${entry.index}`} className="msg" data-role={m.role}>
            <div className="msg-head">
              <span className="msg-who">{mine ? "You" : agentName}</span>
              <time dateTime={m.created_at}>{clock(m.created_at)}</time>
            </div>
            <div className="msg-body">
              {questions.length > 0 ? (
                <>
                  {m.data.summary && <Paragraphs text={m.data.summary} />}
                  <p className="msg-lead">Before I write anything I need to know:</p>
                  <Questions questions={questions} answers={answers} active={canAnswer && entry.index === lastQuestions} onPick={onPick} />
                </>
              ) : (
                <Paragraphs text={m.text} />
              )}
            </div>
          </li>
        );
      })}
      {busy && (
        <li className="msg msg-working" data-role="agent" aria-live="polite">
          <div className="msg-head">
            <span className="msg-who">{agentName}</span>
          </div>
          <div className="msg-body">
            <span className="working-bar" aria-hidden="true" />
            <p className="working-text">Working on it</p>
          </div>
        </li>
      )}
    </ol>
  );
}
