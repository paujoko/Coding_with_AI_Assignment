import { useEffect, useState } from "react";
import type { ActionInfo, Question } from "../api/types";

interface Props {
  actions: ActionInfo[];
  questions: Question[];
  disabled: boolean;
  onRun: (action: string, input: Record<string, string>) => void;
}

// Builds the form for each action from the JSON schema the backend publishes,
// so a new action in a wing shows up here without frontend changes.
export function ActionComposer({ actions, questions, disabled, onRun }: Props) {
  const [active, setActive] = useState(actions[0]?.name ?? "");
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (questions.length && actions.some((a) => a.name === "answer")) setActive("answer");
    else if (!actions.some((a) => a.name === active)) setActive(actions[0]?.name ?? "");
  }, [actions, questions.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const action = actions.find((a) => a.name === active);
  if (!action) return null;
  const fields = Object.entries(action.input_schema.properties ?? {});
  const required = new Set(action.input_schema.required ?? []);
  const key = (field: string) => `${action.name}.${field}`;
  const missing = fields.some(([f]) => required.has(f) && !(values[key(f)] ?? "").trim());

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (missing || disabled) return;
    const input = Object.fromEntries(fields.map(([f]) => [f, (values[key(f)] ?? "").trim()]).filter(([, v]) => v !== ""));
    onRun(action.name, input);
    setValues((v) => Object.fromEntries(Object.entries(v).filter(([k]) => !k.startsWith(`${action.name}.`))));
  };

  const pick = (q: Question, option: string) => {
    const field = key("answers");
    const lines = (values[field] ?? "").split("\n").filter((l) => l.trim() && !l.startsWith(`${q.id}:`));
    setValues({ ...values, [field]: [...lines, `${q.id}: ${option}`].join("\n") });
  };

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
      {fields.map(([field, schema]) => (
        <label key={field} className="field">
          <span>{schema.description ?? field}</span>
          <textarea
            rows={field === "description" || field === "answers" ? 5 : 3}
            value={values[key(field)] ?? ""}
            onChange={(e) => setValues({ ...values, [key(field)]: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(e);
            }}
          />
        </label>
      ))}
      <div className="composer-foot">
        <button type="submit" className="primary" disabled={disabled || missing}>
          {action.label}
        </button>
        <span className="kbd-hint">Ctrl + Enter</span>
      </div>
    </form>
  );
}
