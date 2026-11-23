import { type Block, blocks } from "../components/RichText";

// An agent reply as the developer reads it: the first paragraph, and whatever must be read, are always visible; the
// rest sits behind "Show more". Nothing is cut: expanding shows the whole text.

export const FOLD_AFTER_LINES = 3;
export const LIST_LIMIT = 3;

// Lines that must be read in any case: open questions, failures. Never folded away.
const MUST_READ = /\b(fail(ed|ing|s|ure|ures)?|errors?|open questions?|needs? your|could not|cannot|blocked)\b/i;

const lines = (b: Block): number => (b.kind === "p" ? b.lines.length : b.kind === "list" ? b.items.length : b.text.split("\n").length);
const text = (b: Block): string => (b.kind === "p" ? b.lines.join(" ") : b.kind === "list" ? b.items.join(" ") : "");

export interface FoldedReply {
  all: Block[];
  visible: Block[]; // what shows while folded
  hiddenLines: number; // 0: nothing to fold
}

/** Which blocks stay visible while a reply is folded. A reply of up to three lines is never folded. */
export function foldReply(source: string): FoldedReply {
  const all = blocks(source);
  const total = all.reduce((n, b) => n + lines(b), 0);
  if (total <= FOLD_AFTER_LINES) return { all, visible: all, hiddenLines: 0 };
  const keep = all.map((b, i) => i === 0 || (b.kind !== "code" && MUST_READ.test(text(b))));
  let visible = all.filter((_, i) => keep[i]);
  // A long list in the visible part is cut to three items; the rest comes with "Show more".
  visible = visible.map((b) => (b.kind === "list" && b.items.length > LIST_LIMIT && !MUST_READ.test(text(b)) ? { ...b, items: b.items.slice(0, LIST_LIMIT) } : b));
  const shown = visible.reduce((n, b) => n + lines(b), 0);
  return { all, visible, hiddenLines: Math.max(0, total - shown) };
}

/** The reply without the lines that are shown separately (the drift list), compared by their text. */
export function withoutLines(source: string, drop: string[]): string {
  if (drop.length === 0) return source;
  const gone = new Set(drop.map((d) => d.trim()));
  const isGone = (l: string | undefined) => l !== undefined && gone.has(l.replace(/^\s*[-*]\s+/, "").trim());
  const all = source.split("\n");
  // A lead-in such as "Design and code disagree:" goes with the list it introduced.
  return all
    .filter((l, i) => !isGone(l) && !(l.trimEnd().endsWith(":") && isGone(all[i + 1])))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
