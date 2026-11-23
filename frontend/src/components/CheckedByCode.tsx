import { Icon } from "./Icon";

export const CHECKED_BY_CODE = "Checked by code";

// The one label for everything a program computed and no model wrote (coverage, drift, test results,
// deployment checks, folder sync). Always the same words, so it reads as evidence, not as prose.
export function CheckedByCode() {
  return (
    <span className="by-code" title="Computed by a program from the project's files and trace IDs. No model was asked.">
      <Icon name="code" size={12} />
      {CHECKED_BY_CODE}
    </span>
  );
}

/** Splits a speaker such as "Folder sync, checked by code" into its name and whether it carries the label. */
export function speakerParts(speaker: string): { name: string; byCode: boolean } {
  const m = speaker.match(/^(.*?)[,\s]*\(?checked by code\)?\s*$/i);
  return m ? { name: m[1].trim(), byCode: true } : { name: speaker, byCode: false };
}
