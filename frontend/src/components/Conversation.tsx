import { useEffect, useRef } from "react";
import type { Message } from "../api/types";

export function Conversation({ messages, busy }: { messages: Message[]; busy: boolean }) {
  // Scroll only the list to its newest message; scrollIntoView would also scroll the page.
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [messages.length, busy]);

  if (messages.length === 0 && !busy) {
    return <p className="empty">No conversation in this phase yet.</p>;
  }
  return (
    <ol className="conversation" ref={list}>
      {messages.map((m, i) => (
        <li key={i} className={`msg msg-${m.role}`}>
          <span className="msg-who">{m.role === "developer" ? "You" : m.author || "Agent"}</span>
          <p className="msg-text">{m.text}</p>
        </li>
      ))}
      {busy && (
        <li className="msg msg-agent msg-pending" aria-live="polite">
          <span className="msg-who">Agent</span>
          <p className="msg-text">Working on it. Progress appears in the activity log.</p>
        </li>
      )}
    </ol>
  );
}
