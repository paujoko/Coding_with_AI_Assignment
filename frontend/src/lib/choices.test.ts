import { describe, expect, it } from "vitest";
import { choiceDefaults, choiceFields, isChoice, missingChoice, optionLabel } from "./choices";
import { DESIGN_GENERATE } from "./choices.fixture";

describe("choices from an action's schema", () => {
  it("finds the enum and the array-of-enum fields, not free text", () => {
    expect(choiceFields(DESIGN_GENERATE).map(([f]) => f)).toEqual(["kinds", "level"]);
    expect(isChoice({ type: "string" })).toBe(false);
    expect(isChoice({ type: "array", items: { type: "string" } })).toBe(false);
  });

  it("ticks the schema's defaults", () => {
    expect(choiceDefaults(DESIGN_GENERATE)).toEqual({ kinds: ["use_case", "class", "sequence"], level: "simple" });
  });

  it("names a set of ticks below its minimum", () => {
    expect(missingChoice(DESIGN_GENERATE, { kinds: [], level: "simple" })).toBe("kinds");
    expect(missingChoice(DESIGN_GENERATE, { kinds: ["class"], level: "simple" })).toBeNull();
  });

  it("writes options in plain words", () => {
    expect(optionLabel("use_case")).toBe("Use case");
  });
});
