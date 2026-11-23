import { useState } from "react";
import { foldReply, LIST_LIMIT } from "../lib/reply";
import { CheckedByCode } from "./CheckedByCode";
import { RichText } from "./RichText";

// An agent reply: short ones show whole; long ones show the first paragraph and whatever must be read
// (open questions, failures), and open on "Show more". Reading level 2: read when curious.
export function Reply({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const folded = foldReply(text);
  const fold = folded.hiddenLines > 0;
  return (
    <div className="reply" data-folded={(fold && !open) || undefined}>
      <RichText blocks={fold && !open ? folded.visible : folded.all} />
      {fold && (
        <button type="button" className="link reply-more" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

// A list of lines that are mostly information: the first three, the rest folded.
export function FoldList({ items, className, limit = LIST_LIMIT }: { items: string[]; className?: string; limit?: number }) {
  const [open, setOpen] = useState(false);
  const shown = open ? items : items.slice(0, limit);
  return (
    <>
      <ul className={className}>
        {shown.map((d) => (
          <li key={d}>{d}</li>
        ))}
      </ul>
      {items.length > limit && (
        <button type="button" className="link fold-more" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Show fewer" : `Show ${items.length - limit} more`}
        </button>
      )}
    </>
  );
}

/** "3 differences between the class diagram and the code": a plain headline, the first lines, the rest folded.
 * Not an error: a program in several languages is only read where the checker understands it. */
export function driftHeadline(n: number): string {
  return n === 1 ? "1 difference between the class diagram and the code" : `${n} differences between the class diagram and the code`;
}

export function DriftList({ lines }: { lines: string[] }) {
  return (
    <div className="drift-box">
      <p className="drift-head">
        {driftHeadline(lines.length)} <CheckedByCode />
      </p>
      <FoldList items={lines} className="drift" />
    </div>
  );
}

