import { useEffect, useState } from "react";
import type { ActionInfo, JsonSchemaProperty, Question } from "../api/types";

interface Props {
  actions: ActionInfo[];
  questions: Question[];
  disabled: boolean;
  onRun: (action: string, input: Record<string, unknown>) => Promise<boolean>; // true when the action succeeded
}

type Value = string | boolean;

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

// Builds the form for each action from the JSON schema the backend publishes,
// so a new action in a wing shows up here without frontend changes.
export function ActionComposer({ actions, questions, disabled, onRun }: Props) {
  const [active, setActive] = useState(actions[0]?.name ?? "");
  const [values, setValues] = useState<Record<string, Value>>({});

  useEffect(() => {
    if (questions.length && actions.some((a) => a.name === "answer")) setActive("answer");
    else if (!actions.some((a) => a.name === active)) setActive(actions[0]?.name ?? "");
  }, [actions, questions.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const action = actions.find((a) => a.name === active);
  if (!action) return null;
  const fields = Object.entries(action.input_schema.properties ?? {});
  const required = new Set(action.input_schema.required ?? []);
  const key = (field: string) => `${action.name}.${field}`;
  const missing = fields.some(([f, s]) => required.has(f) && toInput(s, values[key(f)]) === undefined);

  const submit = async (e: React.FormEvent | React.KeyboardEvent) => {
    e.preventDefault();
    if (missing || disabled) return;
    const input = Object.fromEntries(
      fields.map(([f, s]) => [f, toInput(s, values[key(f)])]).filter(([, v]) => v !== undefined),
    );
    // Keep what the developer typed until the backend accepted it.
    if (await onRun(action.name, input)) {
      setValues((v) => Object.fromEntries(Object.entries(v).filter(([k]) => !k.startsWith(`${action.name}.`))));
    }
  };

  const pick = (q: Question, option: string) => {
    const field = key("answers");
    const current = typeof values[field] === "string" ? (values[field] as string) : "";
    const lines = current.split("\n").filter((l) => l.trim() && !l.startsWith(`${q.id}:`));
    setValues({ ...values, [field]: [...lines, `${q.id}: ${option}`].join("\n") });
  };

  const set = (field: string, value: Value) => setValues({ ...values, [key(field)]: value });

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-tabs" role="tablist" aria-label="Actions">
        {actions.map((a) => (
          <button key={a.name} type="button" role="tab" aria-selected={a.name === active} onClick={() => setActive(a.name)}>
            {a.label}
          </button>
        ))}
      </div>
      <p className="composer-hint">{action.description}</p>
      {action.name === "answer" && questions.length > 0 && (
        <ul className="questions">
          {questions.map((q) => (
            <li key={q.id}>
              <p>
                <strong>{q.id}</strong> {q.question}
              </p>
              <p className="why">{q.why}</p>
              {q.options.length > 0 && (
                <div className="options">
                  {q.options.map((o) => (
                    <button key={o} type="button" className="chip" onClick={() => pick(q, o)}>
                      {o}
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {fields.map(([field, schema]) => {
        const label = schema.description ?? field;
        const value = values[key(field)];
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
              <span>{label}</span>
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
              <span>{label}</span>
              <input type="number" value={(value as string) ?? ""} onChange={(e) => set(field, e.target.value)} />
            </label>
          );
        }
        return (
          <label key={field} className="field">
            <span>
              {label}
              {schema.type === "array" ? " (one per line)" : ""}
            </span>
            <textarea
              rows={field === "description" || field === "answers" ? 5 : 3}
              value={(value as string) ?? ""}
              onChange={(e) => set(field, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(e);
              }}
            />
          </label>
        );
      })}
      <div className="composer-foot">
        <button type="submit" className="primary" disabled={disabled || missing}>
          {action.label}
        </button>
        <span className="kbd-hint">Ctrl + Enter</span>
      </div>
    </form>
  );
}
