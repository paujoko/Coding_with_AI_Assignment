import type { ActionInfo, Attachment, Message } from "../api/types";
import type { Values } from "../components/Composer";

/**
 * A message the developer sent that the backend has not saved yet. The backend saves the developer's words only
 * together with the agent's reply (all or nothing, `run_action` in the orchestrator), which can take minutes.
 * Until then the conversation shows this bubble; if the run fails it stays, marked "Not sent".
 */
export interface Outgoing {
  id: number;
  project: string;
  phase: string;
  action: string;
  input: Record<string, unknown>;
  attachments: string[];
  message: Message;
  state: "sending" | "failed";
  seen: number; // developer messages with the same words in this step when it was sent
}

const sameWords = (messages: Message[], text: string) => messages.filter((m) => m.role === "developer" && m.text === text).length;

/** What the backend will save as the developer's message for this action, or null when it saves none. */
export function outgoing(o: {
  id: number;
  project: string;
  phase: string;
  action: ActionInfo | undefined;
  input: Record<string, unknown>;
  attachments: string[];
  documents: Attachment[];
  seen: Message[]; // the step's saved messages when it was sent
  now: string;
}): Outgoing | null {
  if (!o.action) return null;
  // Mirrors the orchestrator: the action's message field, else its label when documents go with it.
  const raw = o.action.message_field ? o.input[o.action.message_field] : undefined;
  let text = typeof raw === "string" ? raw : raw === undefined || raw === null ? "" : String(raw);
  if (!text && o.attachments.length > 0) text = o.action.label;
  if (!text) return null;
  const refs = o.attachments.map((id) => ({ id, name: o.documents.find((d) => d.id === id)?.name ?? "document" }));
  return {
    id: o.id,
    project: o.project,
    phase: o.phase,
    action: o.action.name,
    input: o.input,
    attachments: o.attachments,
    message: { phase: o.phase, role: "developer", text, author: "developer", data: refs.length ? { attachments: refs } : {}, created_at: o.now },
    state: "sending",
    seen: sameWords(o.seen, text),
  };
}

/** The bubbles still to show: a sending one until the backend's saved messages hold its words once more. */
export function unsent(messages: Message[], outbox: Outgoing[]): Outgoing[] {
  return outbox.filter((o) => o.state === "failed" || sameWords(messages, o.message.text) <= o.seen);
}

/** The box without the words that were sent (Try again sends them from the bubble); anything new stays. */
export function withoutSent(values: Values, action: string, input: Record<string, unknown>): Values {
  return Object.fromEntries(
    Object.entries(values).filter(([k, v]) => {
      if (!k.startsWith(`${action}.`)) return true;
      const sent = input[k.slice(action.length + 1)];
      return !(typeof v === "string" && typeof sent === "string" && v.trim() === sent.trim());
    }),
  );
}
