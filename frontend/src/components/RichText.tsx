import type { ReactNode } from "react";

// Chat text as people and models write it: paragraphs, "- " lists, `inline code`, and code blocks, either
// fenced with ``` or indented by four spaces. Code keeps its indentation and scrolls sideways instead of
// running under the results panel (session s04: a fix the debugger proposed lost its indentation and overflowed).
// Deliberately small: no HTML, no links, nothing the text could inject.

export type Block = { kind: "p"; lines: string[] } | { kind: "list"; items: string[] } | { kind: "code"; text: string };

const INDENT = /^( {4}|\t)/;

export function blocks(text: string): Block[] {
  const out: Block[] = [];
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let para: string[] = [];
  let list: string[] = [];
  const flush = () => {
    if (para.length) out.push({ kind: "p", lines: para });
    if (list.length) out.push({ kind: "list", items: list });
    para = [];
    list = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trimStart().startsWith("```")) {
      flush();
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) code.push(lines[i++]);
      out.push({ kind: "code", text: code.join("\n") });
      continue;
    }
    // An indented block starts after a blank line or a line ending with ":" ("replace the branch:").
    const after = i === 0 || lines[i - 1].trim() === "" || lines[i - 1].trimEnd().endsWith(":");
    if (INDENT.test(line) && line.trim() && after && list.length === 0) {
      flush();
      const code: string[] = [];
      while (i < lines.length && (INDENT.test(lines[i]) || (lines[i].trim() === "" && INDENT.test(lines[i + 1] ?? "")))) code.push(lines[i++]);
      i--;
      const cut = Math.min(...code.filter((l) => l.trim()).map((l) => l.match(/^\s*/)?.[0].length ?? 0));
      out.push({ kind: "code", text: code.map((l) => l.slice(cut)).join("\n") });
      continue;
    }
    if (!line.trim()) {
      flush();
      continue;
    }
    const item = line.match(/^\s*[-*]\s+(.*)$/);
    if (item) {
      if (para.length) {
        out.push({ kind: "p", lines: para });
        para = [];
      }
      list.push(item[1]);
    } else {
      if (list.length) {
        out.push({ kind: "list", items: list });
        list = [];
      }
      para.push(line);
    }
  }
  flush();
  return out;
}

function inline(text: string): ReactNode[] {
  return text.split(/(`[^`\n]+`)/g).map((part, i) =>
    part.length > 2 && part.startsWith("`") && part.endsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> : part,
  );
}

export function RichText({ text, blocks: given, listLimit }: { text?: string; blocks?: Block[]; listLimit?: number }) {
  return (
    <>
      {(given ?? blocks(text ?? "")).map((b, i) => {
        if (b.kind === "code")
          return (
            <pre key={i} className="msg-code">
              <code>{b.text}</code>
            </pre>
          );
        if (b.kind === "list")
          return (
            <ul key={i} className="msg-list">
              {(listLimit ? b.items.slice(0, listLimit) : b.items).map((it, j) => (
                <li key={j}>{inline(it)}</li>
              ))}
            </ul>
          );
        return (
          <p key={i}>
            {b.lines.map((line, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {inline(line)}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}
