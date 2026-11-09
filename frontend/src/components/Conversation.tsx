import { useEffect, useRef } from "react";
import type { ActivityEvent, Message, Question } from "../api/types";
import { eventLabel } from "../lib/status";
import { Icon } from "./Icon";

interface Props {
  messages: Message[];
  events: ActivityEvent[]; // this phase's events, shown between the messages as quiet system lines
  agentName: string;
  busy: boolean;
  answers: Record<string, string>; // question id -> chosen option
  canAnswer: boolean;
  onPick: (questionId: string, option: string) => void;
}

// Events worth seeing in the conversation; the full log is in the Activity view.
const INLINE = new Set(["action.started", "agent.llm_call", "artifact.saved", "phase.stale", "phase.approved", "phase.reopened", "phase.error"]);

type Entry = { at: string; message: Message; index: number } | { at: string; event: ActivityEvent };

const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

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
          <p className="question-text">
            <span className="question-id">{q.id}</span>
            {q.question}
          </p>
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

export function Conversation({ messages, events, agentName, busy, answers, canAnswer, onPick }: Props) {
  // Scroll only the list to its newest entry; scrollIntoView would also scroll the page.
  const list = useRef<HTMLOListElement>(null);
  const shown = events.filter((e) => INLINE.has(e.kind));
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [messages.length, shown.length, busy]);

  const lastQuestions = messages.reduce((last, m, i) => (m.data.questions?.length ? i : last), -1);
  const entries: Entry[] = [
    ...messages.map((message, index) => ({ at: message.created_at, message, index })),
    ...shown.map((event) => ({ at: event.at, event })),
  ].sort((a, b) => a.at.localeCompare(b.at));
  const latest = events.at(-1);

  if (entries.length === 0 && !busy) {
    return (
      <div className="conversation-empty">
        <p>No conversation in this phase yet.</p>
        <p>What you ask and what the {agentName.toLowerCase()} answers appears here, together with every step the system takes.</p>
      </div>
    );
  }

  return (
    <ol className="conversation" ref={list} aria-label="Conversation">
      {entries.map((entry) => {
        if ("event" in entry) {
          const e = entry.event;
          return (
            <li key={`e${e.seq}`} className="sysline" data-kind={e.kind}>
              {e.kind === "phase.error" ? <Icon name="alert" size={14} /> : <span className="sysline-dot" aria-hidden="true" />}
              <span className="sysline-text">
                <span className="sr-only">{eventLabel(e.kind)}: </span>
                {e.summary}
              </span>
              <time dateTime={e.at}>{clock(e.at)}</time>
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
            <p className="working-text">{latest && latest.kind !== "action.finished" ? latest.summary : "Working on it"}</p>
          </div>
        </li>
      )}
    </ol>
  );
}
