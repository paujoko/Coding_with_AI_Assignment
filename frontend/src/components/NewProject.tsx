import { useState } from "react";
import { Icon } from "./Icon";
import { Mark } from "./Mark";

interface Props {
  busy: boolean;
  onCreate: (name: string, description: string) => Promise<boolean>;
}

const EXAMPLES = [
  "A to-do app for a small team: tasks with a due date and someone assigned.",
  "A room booking tool for a student association, with a calendar per room.",
  "A command-line expense tracker that groups spending by month.",
];

// Words that start the "what for" part of a description; the name stops before them.
const STOP = new Set(["for", "with", "that", "which", "where", "who", "to", "in", "on", "so", "and"]);

/** A short project name from the description: the noun phrase it starts with, at most four words. */
export function nameFrom(description: string): string {
  const clause = description.trim().split(/[.,:;!?\n]/)[0] ?? "";
  const words: string[] = [];
  for (const w of clause.replace(/^(an?|the)\s+/i, "").split(/\s+/).filter(Boolean)) {
    if (words.length > 0 && STOP.has(w.toLowerCase())) break;
    words.push(w);
    if (words.length === 4) break;
  }
  const name = words.join(" ");
  return name ? name.charAt(0).toUpperCase() + name.slice(1) : "New project";
}

// The start page works like the start of a chat: say what you want, press Enter.
export function NewProject({ busy, onCreate }: Props) {
  const [description, setDescription] = useState("");
  const ready = description.trim() !== "" && !busy;

  const submit = async () => {
    if (!ready) return;
    if (await onCreate(nameFrom(description), description.trim())) setDescription("");
  };

  return (
    <section className="home" aria-labelledby="home-heading">
      <Mark size={44} />
      <h1 id="home-heading">What do you want to build?</h1>
      <form
        className="composer home-composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="composer-box">
          <label className="field field-main">
            <span className="sr-only">Describe the software</span>
            <textarea
              rows={3}
              value={description}
              autoFocus
              placeholder="Describe the software in a few sentences"
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
          </label>
          <div className="composer-bar">
            <span className="composer-note">Enter to start, Shift+Enter for a new line</span>
            <button type="submit" className="button button-send" disabled={!ready}>
              Start
              <Icon name="send" size={14} />
            </button>
          </div>
        </div>
      </form>
      <div className="examples" role="group" aria-label="Examples">
        {EXAMPLES.map((e) => (
          <button key={e} type="button" className="example" onClick={() => setDescription(e)}>
            {e}
          </button>
        ))}
      </div>
      <p className="home-note">
        Agents turn your idea into requirements, design, code, tests and a deployment. After every step they wait for your approval.
      </p>
    </section>
  );
}
