/** "agent:analyst" -> "Analyst", "developer" -> "you". */
export function authorName(author: string): string {
  if (author === "developer") return "you";
  const name = author.replace(/^agent:/, "");
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** Save text as a file (requirements.md, a .puml source) without a server round trip. */
export function downloadText(filename: string, text: string, type = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
