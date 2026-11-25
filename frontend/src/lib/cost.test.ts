import { describe, expect, it } from "vitest";
import type { ActivityEvent } from "../api/types";
import { llmCost, usd } from "./cost";

const event = (kind: string, data: Record<string, unknown>): ActivityEvent => ({ seq: 1, at: "2026-11-25T10:00:00Z", kind, phase: "requirements", summary: "", data });

describe("llmCost", () => {
  it("shows tokens and the cost of a priced answer", () => {
    const e = event("agent.llm_call", { model: "claude-sonnet-5-5", usage: { prompt_tokens: 12345, completion_tokens: 678 }, cost_usd: 0.0315 });
    expect(llmCost(e)).toBe("12,345 tokens in, 678 out, $0.0315");
  });

  it("says cost unknown instead of $0 when no price is known", () => {
    const e = event("agent.llm_call", { model: "gpt-5", usage: { prompt_tokens: 10, completion_tokens: 5 }, cost_usd: null });
    expect(llmCost(e)).toBe("10 tokens in, 5 out, cost unknown");
    expect(llmCost(event("agent.llm_failed", { model: "gpt-5" }))).toBe("cost unknown");
  });

  it("names the free demo model", () => {
    expect(llmCost(event("agent.llm_call", { model: "mock/analyst", cost_usd: 0 }))).toBe("demo model, no cost");
  });

  it("ignores events that are not model answers", () => {
    expect(llmCost(event("phase.approved", { cost_usd: 1 }))).toBeNull();
  });
});

describe("usd", () => {
  it("keeps small amounts readable", () => {
    expect(usd(0)).toBe("$0");
    expect(usd(0.0012)).toBe("$0.0012");
    expect(usd(1.5)).toBe("$1.50");
  });
});
