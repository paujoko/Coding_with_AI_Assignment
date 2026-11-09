/** "agent:analyst" -> "Analyst", "developer" -> "you". */
export function authorName(author: string): string {
  if (author === "developer") return "you";
  const name = author.replace(/^agent:/, "");
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
