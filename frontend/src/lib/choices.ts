import type { ActionInfo, JsonSchemaProperty } from "../api/types";

// Choices a wing offers before its generator runs (Design: which diagrams, how detailed; Tests: how many).
// They come from the action's JSON schema: a field with an `enum` is one of several, an array of an enum is a
// set of ticks. The schema's `default` is what is ticked at first, so the wing decides the recommendation.

export type ChoiceValue = string | string[];
export type ChoiceValues = Record<string, ChoiceValue>;

export const isChoice = (s: JsonSchemaProperty): boolean => Array.isArray(s.enum) || (s.type === "array" && Array.isArray(s.items?.enum));

/** The choice fields of an action, in schema order. */
export function choiceFields(action: ActionInfo | undefined): [string, JsonSchemaProperty][] {
  return Object.entries(action?.input_schema.properties ?? {}).filter(([, s]) => isChoice(s));
}

/** What is ticked before the developer touches anything: the schema's defaults. */
export function choiceDefaults(action: ActionInfo | undefined): ChoiceValues {
  return Object.fromEntries(
    choiceFields(action).map(([f, s]) => {
      if (s.type === "array") return [f, Array.isArray(s.default) ? s.default.map(String) : []];
      return [f, s.default !== undefined ? String(s.default) : String(s.enum?.[0] ?? "")];
    }),
  );
}

/** The first set of ticks that is below its minimum, if any (e.g. no diagram ticked). */
export function missingChoice(action: ActionInfo | undefined, values: ChoiceValues): string | null {
  const short = choiceFields(action).find(([f, s]) => s.type === "array" && (values[f]?.length ?? 0) < (s.minItems ?? 0));
  return short ? short[0] : null;
}

/** An option as a person reads it: "use_case" -> "Use case". */
export const optionLabel = (o: string) => {
  const words = o.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
};
