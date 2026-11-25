import type { Message } from "../api/types";

/**
 * The kinds of entries in a step's conversation (ADR 0022). The developer's words, their decisions (a choice, a button,
 * an edit by hand: `data.decision`), the agents' replies, and what Wings did on the developer's behalf
 * (role "system", author "wings", `data.on_behalf`). Messages from before API 13 have none of the new fields and read
 * as they always did.
 */
export const isDecision = (m: Message): boolean => !!m.data.decision;

export const byWings = (m: Message): boolean => !!m.data.on_behalf || (m.role === "system" && m.author === "wings");

/** Words the developer typed (not a decision line, not Wings' instruction). */
export const typedByDeveloper = (m: Message): boolean => m.role === "developer" && !isDecision(m) && !byWings(m);

/** Who acted, said above what Wings did on the developer's behalf. */
export function behalfLabel(on: Message["data"]["on_behalf"]): string {
  if (on && typeof on.change === "number") return `Wings, carrying change #${on.change}`;
  return "Wings, redoing this step";
}

export interface Answered {
  id: string;
  question: string;
  answer: string;
}

/**
 * The developer's answers ("Q1: Terminal", one per line) next to the questions they answer, taken from the latest
 * message before them that asked questions. Null when any line is not an answer to one of those questions.
 */
export function answersWithQuestions(messages: Message[], index: number): Answered[] | null {
  const lines = messages[index].text.split("\n").filter((l) => l.trim());
  if (!lines.length) return null;
  const asked = messages
    .slice(0, index)
    .reverse()
    .find((x) => x.data.questions?.length);
  if (!asked) return null;
  const out: Answered[] = [];
  for (const line of lines) {
    const hit = /^\s*(Q\d+)\s*[:.]\s*(.+)$/.exec(line);
    const q = hit && asked.data.questions?.find((x) => x.id === hit[1]);
    if (!hit || !q) return null;
    out.push({ id: q.id, question: q.question, answer: hit[2].trim() });
  }
  return out;
}
