import { useState } from "react";
import type { PhaseInfo } from "../api/types";
import { Icon } from "./Icon";

interface Props {
  catalog: PhaseInfo[];
  busy: boolean;
  first: boolean; // no project exists yet
  onCreate: (name: string, description: string) => Promise<boolean>;
}

const WING = ["Left wing", "Left wing", "Left wing", "Body", "Right wing", "Right wing", "Right wing"];

export function NewProject({ catalog, busy, first, onCreate }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const ready = name.trim() !== "";

  const submit = async (withDescription: boolean) => {
    if (!ready || busy) return;
    if (await onCreate(name.trim(), withDescription ? description.trim() : "")) {
      setName("");
      setDescription("");
    }
  };

  return (
    <section className="page start" aria-labelledby="start-heading">
      <div className="start-form">
        <header className="page-head">
          <h1 id="start-heading">{first ? "What do you want to build?" : "New project"}</h1>
          <p className="lede">
            Describe the software in a few sentences. The agents turn it into requirements, a UML design, code, tests and a deployment, and
            stop after every phase so you can review, change and approve what they made.
          </p>
        </header>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(description.trim() !== "");
          }}
        >
          <label className="field">
            <span className="field-label">Project name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Team to-do list" maxLength={120} autoFocus />
          </label>
          <label className="field">
            <span className="field-label">Description</span>
            <textarea
              rows={6}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A small to-do app for a team. Tasks have a title, a due date and someone assigned. People see what is open and mark tasks as done."
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(description.trim() !== "");
              }}
            />
          </label>
          <div className="row-actions">
            <button type="button" className="button button-quiet" disabled={!ready || busy} onClick={() => submit(false)}>
              Create without description
            </button>
            <button type="submit" className="button button-primary" disabled={!ready || !description.trim() || busy}>
              Create and start
              <Icon name="arrowRight" size={14} />
            </button>
          </div>
        </form>
      </div>

      <aside className="how" aria-labelledby="how-heading">
        <h2 id="how-heading">How a project moves</h2>
        <ol>
          {catalog.map((c, i) => (
            <li key={c.id} data-planned={!c.implemented || undefined}>
              <span className="how-number">P{i + 1}</span>
              <span className="how-title">
                {c.title}
                <span className="how-wing">{WING[i]}</span>
              </span>
              <span className="how-summary">{c.summary}</span>
            </li>
          ))}
        </ol>
      </aside>
    </section>
  );
}
