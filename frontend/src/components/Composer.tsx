import { useEffect, useRef } from "react";
import type { ActionInfo, JsonSchemaProperty } from "../api/types";
import { ACCEPT, type PendingFile } from "../lib/attachments";
import { PendingChips } from "./FileChips";
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
  onRun: (action: string, input: Record<string, unknown>, attachments: string[]) => Promise<boolean>; // true when it succeeded
  files?: PendingFile[]; // documents attached to this message (upload handled by the parent)
  onAddFiles?: (files: File[]) => void; // without it there is no attach button
  onRemoveFile?: (key: string) => void;
  focusSignal?: number; // changes when the parent wants the cursor in the text box
}

// Turns the form value into what the field's JSON schema expects; undefined means "leave it out".
export function toInput(schema: JsonSchemaProperty, value: Value | undefined): unknown {
  if (schema.type === "boolean") return Boolean(value);
  const text = typeof value === "string" ? value.trim() : "";
  if (text === "") return undefined;
  if (schema.type === "integer") return Number.parseInt(text, 10);
  if (schema.type === "number") return Number(text);
  if (schema.type === "array")
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
  return text;
}

const rowsFor = (text: string) => Math.min(10, Math.max(2, text.split("\n").length)); // two lines fit every placeholder

// The chat input. Fields come from the action's JSON schema, so a new action in a wing
// shows up here without frontend changes. Layout as in chat apps: text first, then a bar
// with attach, the action to run and the round send button.
export function Composer(p: Props) {
  const { actions, values, disabled } = p;
  const box = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (p.focusSignal) box.current?.focus();
  }, [p.focusSignal]);

  const action = actions.find((a) => a.name === p.active) ?? actions[0];
  if (!action) return null;
  const fields = Object.entries(action.input_schema.properties ?? {});
  const required = new Set(action.input_schema.required ?? []);
  const key = (field: string) => `${action.name}.${field}`;
  const missing = fields.some(([f, s]) => required.has(f) && toInput(s, values[key(f)]) === undefined);
  const files = p.files ?? [];
  const uploading = files.some((f) => f.status === "uploading");
  const single = fields.length === 1;

  const submit = async (e: React.FormEvent | React.KeyboardEvent) => {
    e.preventDefault();
    if (missing || disabled || uploading) return;
    const input = Object.fromEntries(fields.map(([f, s]) => [f, toInput(s, values[key(f)])]).filter(([, v]) => v !== undefined));
    const ids = files.filter((f) => f.status === "ready").map((f) => f.attachment!.id);
    // Keep what the developer typed until the backend accepted it.
    if (await p.onRun(action.name, input, ids)) {
      p.onValues(Object.fromEntries(Object.entries(values).filter(([k]) => !k.startsWith(`${action.name}.`))));
    }
  };

  const set = (field: string, value: Value) => p.onValues({ ...values, [key(field)]: value });

  return (
    <form className="composer" onSubmit={submit} aria-label="Message to the agent">
      <div className="composer-box">
        {p.onRemoveFile && <PendingChips files={files} onRemove={p.onRemoveFile} />}
        {fields.map(([field, schema], i) => {
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
                ref={i === 0 ? box : undefined}
                rows={rowsFor(text)}
                value={text}
                placeholder={single ? `${label}${optional && !/optional/i.test(label) ? " (optional)" : ""}` : undefined}
                onChange={(e) => set(field, e.target.value)}
                onPaste={(e) => {
                  const pasted = Array.from(e.clipboardData.files);
                  if (pasted.length && p.onAddFiles) {
                    e.preventDefault();
                    p.onAddFiles(pasted);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(e);
                }}
              />
            </label>
          );
        })}
        <div className="composer-bar">
          <div className="composer-tools">
            {p.onAddFiles && (
              <>
                <input
                  ref={picker}
                  type="file"
                  multiple
                  accept={ACCEPT}
                  hidden
                  onChange={(e) => {
                    if (e.target.files?.length) p.onAddFiles!(Array.from(e.target.files));
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Attach documents"
                  title="Attach documents (text, Markdown, PDF, Word)"
                  disabled={disabled}
                  onClick={() => picker.current?.click()}
                >
                  <Icon name="paperclip" />
                </button>
              </>
            )}
            {actions.length > 1 && (
              <div className="composer-actions" role="group" aria-label="What to do">
                {actions.map((a) => (
                  <button
                    key={a.name}
                    type="button"
                    aria-pressed={a.name === action.name}
                    title={a.description}
                    onClick={() => p.onActive(a.name)}
                  >
                    {a.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            type="submit"
            className="send"
            aria-label={action.label}
            title={`${action.label}: ${action.description} (Ctrl+Enter)`}
            disabled={disabled || missing || uploading}
          >
            <Icon name={disabled ? "spinner" : "arrowUp"} className={disabled ? "spin" : undefined} />
          </button>
        </div>
      </div>
    </form>
  );
}
