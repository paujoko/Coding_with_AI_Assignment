import type { ActivityEvent } from "../api/types";

const LLM_EVENTS = new Set(["agent.llm_call", "agent.llm_failed"]);

/** "$0.0123" with enough digits that a cheap call does not read as nothing. */
export function usd(amount: number): string {
  if (amount === 0) return "$0";
  return amount >= 0.1 ? `$${amount.toFixed(2)}` : `$${amount.toFixed(4)}`;
}

/**
 * Tokens and cost of one model answer, for the Activity view: "1,234 tokens in, 56 out, $0.0012".
 * The backend sends cost_usd null when no price is known (OpenAI, an unknown Claude model):
 * that reads "cost unknown", never "$0". The free demo model says so. Null for other events.
 */
export function llmCost(event: ActivityEvent): string | null {
  if (!LLM_EVENTS.has(event.kind)) return null;
  const data = event.data;
  const model = typeof data.model === "string" ? data.model : "";
  if (model.startsWith("mock/")) return "demo model, no cost";
  const usage = (data.usage ?? {}) as Record<string, unknown>;
  const tokensIn = typeof usage.prompt_tokens === "number" ? usage.prompt_tokens : null;
  const tokensOut = typeof usage.completion_tokens === "number" ? usage.completion_tokens : null;
  const parts: string[] = [];
  if (tokensIn !== null && tokensOut !== null) {
    parts.push(`${tokensIn.toLocaleString("en-US")} tokens in, ${tokensOut.toLocaleString("en-US")} out`);
  }
  parts.push(typeof data.cost_usd === "number" ? usd(data.cost_usd) : "cost unknown");
  return parts.join(", ");
}
