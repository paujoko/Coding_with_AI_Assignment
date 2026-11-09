import { ACTION_LABEL, ACTION_MEANING, type DisplayStatus } from "../lib/status";
import { Icon } from "./Icon";

const ORDER: DisplayStatus[] = ["ready", "needs_input", "draft", "approved", "stale", "locked", "planned"];

// The loop every step follows, and what the word under each step means.
export function HowItWorks({ onClose }: { onClose: () => void }) {
  return (
    <section className="how-it-works" aria-labelledby="how-heading">
      <header>
        <h2 id="how-heading">How it works</h2>
        <button type="button" className="icon-button icon-button-sm" aria-label="Close" onClick={onClose}>
          <Icon name="close" size={14} />
        </button>
      </header>
      <ol className="how-steps">
        <li>
          <strong>Talk to the agent of a step.</strong> Describe what you want, answer its questions, attach documents.
        </li>
        <li>
          <strong>Check the result</strong> on the right. Edit it, or ask for changes in the chat.
        </li>
        <li>
          <strong>Approve it.</strong> The next step unlocks. Change an earlier step later, and the steps after it say Update.
        </li>
      </ol>
      <dl className="legend">
        {ORDER.map((s) => (
          <div key={s} data-status={s}>
            <dt>
              <span className="legend-node" aria-hidden="true" />
              {ACTION_LABEL[s]}
            </dt>
            <dd>{ACTION_MEANING[s]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
