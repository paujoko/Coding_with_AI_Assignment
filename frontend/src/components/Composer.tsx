import type { ActionInfo, JsonSchemaProperty } from "../api/types";
import { Icon } from "./Icon";

export type Value = string | boolean;
export type Values = Record<string, Value>; // key: "<action>.<field>"

interface Props {
  actions: ActionInfo[];
  active: string;
  onActive: (name: string) => void;
  values: Values;
  onValues: (values: Values) => void;
  disabled: boolean;
  onRun: (action: string, input: Record<string, unknown>) => Promise<boolean>; // true when the action succeeded
}

// Turns the form value into what the field's JSON schema expects; undefined means "leave it out".
export function toInput(schema: JsonSchemaProperty, value: Value | undefined): unknown {
  if (schema.type === "boolean") return Boolean(value);
  const text = typeof value === "string" ? value.trim() : "";
  if (text === "") return undefined;
  if (schema.type === "integer") return Number.parseInt(text, 10);
  if (schema.type === "number") return Number(text);
  if (schema.type === "array") return text.split("\n").map((l) => l.trim()).filter(Boolean);
  return text;
}

const rowsFor = (text: string, min: number) => Math.min(10, Math.max(min, text.split("\n").length));

// Builds the form for each action from the JSON schema the backend publishes,
// so a new action in a wing shows up here without frontend changes.
export function Composer({ actions, active, onActive, values, onValues, disabled, onRun }: Props) {
  const action = actions.find((a) => a.name === active) ?? actions[0];
  if (!action) return null;
  const fields = Object.entries(action.input_schema.properties ?? {});
  const required = new Set(action.input_schema.required ?? []);
  const key = (field: string) => `${action.name}.${field}`;
  const missing = fields.some(([f, s]) => required.has(f) && toInput(s, values[key(f)]) === undefined);
  const single = fields.length === 1;

  const submit = async (e: React.FormEvent | React.KeyboardEvent) => {
    e.preventDefault();
    if (missing || disabled) return;
    const input = Object.fromEntries(fields.map(([f, s]) => [f, toInput(s, values[key(f)])]).filter(([, v]) => v !== undefined));
    // Keep what the developer typed until the backend accepted it.
    if (await onRun(action.name, input)) {
      onValues(Object.fromEntries(Object.entries(values).filter(([k]) => !k.startsWith(`${action.name}.`))));
    }
  };

  const set = (field: string, value: Value) => onValues({ ...values, [key(field)]: value });

  return (
    <form className="composer" onSubmit={submit} aria-label="Ask the agent">
      {actions.length > 1 && (
        <div className="composer-actions" role="tablist" aria-label="What to do">
          {actions.map((a) => (
            <button
              key={a.name}
              type="button"
              role="tab"
              aria-selected={a.name === action.name}
              title={a.description}
              onClick={() => onActive(a.name)}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
      {fields.map(([field, schema]) => {
        const label = schema.description ?? field;
        const value = values[key(field)];
        const optional = !required.has(field);
        if (schema.type === "boolean") {
          return (
            <label key={field} className="field field-check">
              <input type="checkbox" checked={Boolean(value)} onChange={(e) => set(field, e.target.checked)} />
              <span>{label}</span>
            </label>
          );
        }
        if (schema.enum) {
          return (
            <label key={field} className="field">
              <span className="field-label">{label}</span>
              <select value={(value as string) ?? ""} onChange={(e) => set(field, e.target.value)}>
                <option value="">Choose</option>
                {schema.enum.map((o) => (
                  <option key={String(o)} value={String(o)}>
                    {String(o)}
                  </option>
                ))}
              </select>
            </label>
          );
        }
        if (schema.type === "integer" || schema.type === "number") {
          return (
            <label key={field} className="field">
              <span className="field-label">{label}</span>
              <input type="number" value={(value as string) ?? ""} onChange={(e) => set(field, e.target.value)} />
            </label>
          );
        }
        const text = (value as string) ?? "";
        return (
          <label key={field} className={single ? "field field-main" : "field"}>
            <span className={single ? "sr-only" : "field-label"}>
              {label}
              {schema.type === "array" ? " (one per line)" : ""}
            </span>
            <textarea
              rows={rowsFor(text, single ? 3 : 2)}
              value={text}
              placeholder={single ? `${label}${optional ? " (optional)" : ""}` : undefined}
              onChange={(e) => set(field, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(e);
              }}
            />
          </label>
        );
      })}
      <div className="composer-foot">
        <p className="composer-hint">{action.description}</p>
        <span className="kbd-hint" aria-hidden="true">
          <kbd>Ctrl</kbd> <kbd>Enter</kbd>
        </span>
        <button type="submit" className="button button-primary" disabled={disabled || missing}>
          {action.label}
          <Icon name="send" size={14} />
        </button>
      </div>
    </form>
  );
}
