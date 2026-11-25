import type { ActionInfo } from "../api/types";
import { type ChoiceValues, choiceFields, optionLabel } from "../lib/choices";

interface Props {
  action: ActionInfo;
  values: ChoiceValues;
  onChange: (values: ChoiceValues) => void;
  disabled: boolean;
}

// The choices a step offers before its agent starts (Design: which diagrams and how detailed; Tests: how
// many). Built from the action's JSON schema: an array of an enum is a set of ticks, an enum is one of
// several. The step's solid button starts the agent with what is ticked here.
export function StartChoices({ action, values, onChange, disabled }: Props) {
  const fields = choiceFields(action);
  return (
    <form className="start-choices" aria-label="Choose before the agent starts" onSubmit={(e) => e.preventDefault()}>
      {fields.map(([field, schema]) => {
        const many = schema.type === "array";
        const options = ((many ? schema.items?.enum : schema.enum) ?? []).map(String);
        const hints = schema.option_hints ?? {};
        const current = values[field];
        const ticked = (o: string) => (many ? Array.isArray(current) && current.includes(o) : current === o);
        const toggle = (o: string) => {
          if (!many) return onChange({ ...values, [field]: o });
          const now = Array.isArray(current) ? current : [];
          const next = now.includes(o) ? now.filter((x) => x !== o) : [...now, o];
          onChange({ ...values, [field]: options.filter((x) => next.includes(x)) }); // keep the schema's order
        };
        return (
          <fieldset key={field} className="start-group" data-many={many || undefined} disabled={disabled}>
            <legend>{schema.description ?? optionLabel(field)}</legend>
            <div className="start-options">
              {options.map((o) => (
                <label key={o} className="start-option" data-on={ticked(o) || undefined}>
                  <input type={many ? "checkbox" : "radio"} name={`${action.name}-${field}`} value={o} checked={ticked(o)} onChange={() => toggle(o)} />
                  <span className="start-option-text">
                    <span className="start-option-name">{optionLabel(o)}</span>
                    {hints[o] && <span className="start-option-hint">{hints[o]}</span>}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        );
      })}
    </form>
  );
}
