/** "agent:impact_analyst" -> "Impact analyst", "system:pytest" -> "pytest", "developer" -> "you". */
export function authorName(author: string): string {
  if (author === "developer") return "you";
  if (author.startsWith("system:")) return author.slice(7);
  return agentLabel(author.replace(/^agent:/, ""));
}

/** An agent's name as people write it: "impact_analyst" -> "Impact analyst". */
export const agentLabel = (name: string) => capitalize(name.replace(/_/g, " "));

export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** Save text as a file (requirements.md, a .puml source) without a server round trip. */
export function downloadText(filename: string, text: string, type = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
