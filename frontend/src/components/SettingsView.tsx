import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ConnectionTest, DiagramSettings, Effort, Efforts, LlmSettings, Models, PaidProvider, Provider, Tier } from "../api/types";
import { Icon } from "./Icon";

interface Props {
  onSaved: () => void; // refresh what the rest of the app shows (health, sidebar)
}

const CHOICES: { id: Provider; title: string; text: string; keyUrl?: string; keyLabel?: string; placeholder?: string }[] = [
  { id: "mock", title: "Demo model", text: "Free and offline. Always plays the same to-do app example, whatever you type." },
  {
    id: "openai",
    title: "OpenAI",
    text: "Real answers to your own project. Needs an API key from your OpenAI account.",
    keyUrl: "https://platform.openai.com/api-keys",
    keyLabel: "OpenAI API key",
    placeholder: "sk-...",
  },
  {
    id: "openrouter",
    title: "OpenRouter",
    text: "One key for models of many vendors, some of them free.",
    keyUrl: "https://openrouter.ai/keys",
    keyLabel: "OpenRouter API key",
    placeholder: "sk-or-...",
  },
  {
    id: "anthropic",
    title: "Claude",
    text: "Anthropic's models with your own Anthropic API key. Activity shows the cost of each step.",
    keyUrl: "https://platform.claude.com/settings/keys",
    keyLabel: "Anthropic API key",
    placeholder: "sk-ant-...",
  },
];

// Which agents use which tier: phases/*/module.py in the backend (docs/code/llm.md).
const TIERS: { tier: Tier; who: string }[] = [
  { tier: "small", who: "the connection test" },
  { tier: "mid", who: "most agents" },
  { tier: "frontier", who: "design and debugging" },
];

const EFFORTS: Effort[] = ["low", "medium", "high", "xhigh", "max"];
const EFFORTS_KEY = (e: Efforts) => JSON.stringify(Object.entries(e).sort());

// Choose the model provider and paste a key. The key is stored only on this computer (.env) and never shown again.
export function SettingsView({ onSaved }: Props) {
  const [current, setCurrent] = useState<LlmSettings | null>(null);
  const [provider, setProvider] = useState<Provider>("mock");
  const [key, setKey] = useState("");
  const [models, setModels] = useState<Models | null>(null);
  const [efforts, setEfforts] = useState<Efforts>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [test, setTest] = useState<ConnectionTest | "running" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.settings().then(
      (s) => {
        setCurrent(s);
        setProvider(s.provider);
        setModels(s.provider === "mock" ? null : s.models);
        setEfforts(s.efforts ?? {});
      },
      (e) => setError(e instanceof ApiError ? e.message : String(e)),
    );
  }, []);

  if (error && !current) {
    return (
      <section className="page">
        <header className="page-head">
          <h1>Settings</h1>
        </header>
        <p className="notice">{error}</p>
      </section>
    );
  }
  if (!current) return null;

  const choice = CHOICES.find((c) => c.id === provider)!;
  const paid = provider !== "mock";
  const savedKey = paid ? current.keys[provider as PaidProvider] : null;
  const claude = provider === "anthropic";
  const shownModels = paid
    ? provider === current.provider && models
      ? models
      : (models ?? current.defaults[provider as PaidProvider])
    : null;
  const needsKey = paid && !savedKey?.set && !key.trim();

  const pick = (p: Provider) => {
    setProvider(p);
    setKey("");
    setSaved(false);
    setTest(null);
    setModels(p === "mock" ? null : p === current.provider ? current.models : current.defaults[p as PaidProvider]);
    setEfforts(current.efforts ?? {});
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setTest(null);
    try {
      const next = await api.saveSettings(provider, key.trim(), shownModels, claude ? efforts : null);
      setCurrent(next);
      setKey("");
      setSaved(true);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const runTest = async () => {
    setTest("running");
    try {
      setTest(await api.testSettings());
    } catch (e) {
      setTest({ ok: false, error: e instanceof ApiError ? e.message : String(e) });
    }
  };

  const sameEfforts = !claude || EFFORTS_KEY(efforts) === EFFORTS_KEY(current.efforts ?? {});
  const unchanged =
    provider === current.provider &&
    !key.trim() &&
    JSON.stringify(shownModels) === JSON.stringify(paid ? current.models : null) &&
    sameEfforts;

  return (
    <section className="page settings" aria-labelledby="settings-heading">
      <header className="page-head">
        <h1 id="settings-heading">Settings</h1>
      </header>
      <header className="settings-section-head">
        <h2>AI model</h2>
        <p className="lede">
          Choose which model the agents use. Your key is saved only on this computer, in the file .env next to the code, and is never shown
          again.
        </p>
      </header>

      <fieldset className="choices choices-pairs">
        <legend className="sr-only">Provider</legend>
        {CHOICES.map((c) => (
          <label key={c.id} className="choice" data-checked={provider === c.id || undefined}>
            <input type="radio" name="provider" value={c.id} checked={provider === c.id} onChange={() => pick(c.id)} />
            <span className="choice-title">
              {c.title}
              {current.provider === c.id && <span className="tag">in use</span>}
            </span>
            <span className="choice-text">{c.text}</span>
          </label>
        ))}
      </fieldset>

      {paid && (
        <div className="settings-form">
          <label className="field">
            <span className="field-label">{choice.keyLabel}</span>
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={key}
              placeholder={
                savedKey?.set ? `Saved (${savedKey.hint}). Paste a new key to replace it.` : `Paste your key here (${choice.placeholder})`
              }
              onChange={(e) => {
                setKey(e.target.value);
                setSaved(false);
              }}
            />
            <span className="field-help">
              No key yet? Create one at{" "}
              <a href={choice.keyUrl} target="_blank" rel="noreferrer">
                {choice.keyUrl?.replace("https://", "")} <Icon name="external" size={12} />
              </a>
              . Each agent step is one or two model calls.
            </span>
          </label>

          <details className="advanced">
            <summary>{claude ? "Models and effort" : "Models"}</summary>
            {claude && (
              <p className="field-help model-note">Lower effort answers faster and costs less; the model thinks less. Leave the default if unsure.</p>
            )}
            <div className="model-fields">
              {TIERS.map(({ tier, who }) => (
                <label key={tier} className="field">
                  <span className="field-label">
                    {tier[0].toUpperCase() + tier.slice(1)} <span className="field-help">for {who}</span>
                  </span>
                  <input
                    value={shownModels?.[tier] ?? ""}
                    spellCheck={false}
                    onChange={(e) => {
                      setModels({ ...(shownModels as Models), [tier]: e.target.value });
                      setSaved(false);
                    }}
                  />
                  {claude && (
                    <select
                      aria-label={`Effort for the ${tier} tier`}
                      value={efforts[tier] ?? ""}
                      onChange={(e) => {
                        const next = { ...efforts };
                        if (e.target.value) next[tier] = e.target.value as Effort;
                        else delete next[tier];
                        setEfforts(next);
                        setSaved(false);
                      }}
                    >
                      <option value="">Effort: model default</option>
                      {EFFORTS.map((level) => (
                        <option key={level} value={level}>
                          Effort: {level}
                        </option>
                      ))}
                    </select>
                  )}
                </label>
              ))}
            </div>
          </details>
        </div>
      )}

      {error && <p className="notice">{error}</p>}

      <div className="settings-actions">
        <button type="button" className="button button-primary" onClick={save} disabled={saving || needsKey || unchanged}>
          {saving ? "Saving" : "Save"}
        </button>
        {provider === current.provider && (paid ? current.key_set : true) && (
          <button type="button" className="button" onClick={runTest} disabled={test === "running"}>
            {test === "running" ? "Testing" : "Test connection"}
          </button>
        )}
        {saved && (
          <span className="settings-status" data-ok>
            <Icon name="check" size={14} /> Saved. The agents use {CHOICES.find((c) => c.id === current.provider)?.title} from now on.
          </span>
        )}
      </div>
      {test && test !== "running" && (
        <p className="settings-status" data-ok={test.ok || undefined} role="status">
          <Icon name={test.ok ? "check" : "alert"} size={14} /> {test.ok ? test.message : test.error}
        </p>
      )}
      <DiagramsSection onSaved={onSaved} />
    </section>
  );
}

// How PlantUML diagrams become pictures: plantuml.com (one click) or PlantUML on this computer (private, needs Java).
function DiagramsSection({ onSaved }: { onSaved: () => void }) {
  const [state, setState] = useState<DiagramSettings | null>(null);
  const [working, setWorking] = useState<"server" | "download" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.diagramSettings().then(setState, () => setState(null));
  }, []);
  if (!state) return null;

  const act = async (kind: "server" | "download", work: () => Promise<DiagramSettings>) => {
    setWorking(kind);
    setError(null);
    try {
      setState(await work());
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setWorking(null);
    }
  };

  const status =
    state.mode === "jar"
      ? "Pictures are drawn by PlantUML on this computer."
      : state.mode === "server"
        ? `Pictures are drawn by ${state.server_url?.replace("https://", "")}.`
        : "Pictures are not set up yet: diagrams show as PlantUML source.";

  return (
    <section className="settings-diagrams" aria-labelledby="diagrams-heading">
      <header className="settings-section-head">
        <h2 id="diagrams-heading">Diagrams</h2>
        <p className="settings-status" data-ok={state.mode ? true : undefined}>
          <Icon name={state.mode ? "check" : "alert"} size={14} /> {status}
        </p>
      </header>
      <div className="choices choices-two">
        <div className="choice" data-checked={state.mode === "server" || undefined}>
          <span className="choice-title">Use plantuml.com</span>
          <span className="choice-text">One click, nothing to install. The diagram text is sent to the public PlantUML server to be drawn.</span>
          <button
            type="button"
            className="button"
            disabled={working !== null}
            onClick={() => act("server", () => api.usePublicServer(state.server_url !== state.public_server))}
          >
            {working === "server" ? "Saving" : state.server_url === state.public_server ? "Stop using plantuml.com" : "Use plantuml.com"}
          </button>
        </div>
        <div className="choice" data-checked={state.mode === "jar" || undefined}>
          <span className="choice-title">PlantUML on this computer</span>
          <span className="choice-text">
            Private and offline. Downloads plantuml.jar (about 22 MB) into the tools folder. Needs Java.
            {!state.java && " Java was not found: install Java 17 or newer, restart the backend, then download."}
          </span>
          <button type="button" className="button" disabled={working !== null || !state.java} onClick={() => act("download", api.downloadPlantuml)}>
            {working === "download" ? "Downloading" : state.jar_path ? "Download again" : "Download PlantUML"}
          </button>
        </div>
      </div>
      {error && <p className="notice">{error}</p>}
    </section>
  );
}
