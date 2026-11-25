import type { Work } from "../lib/work";
import { useElapsed } from "./Conversation";
import { Icon } from "./Icon";

interface Props {
  title: string; // the working step's plain name
  state: Work["state"];
  since: string | null; // when the work started, for the timer
  onShow: () => void; // open the working step
}

// One slim line above every screen but the working step: the developer may look around while an agent works,
// and always sees where the work is and how to get back. When it ends, Wings does not jump; this line says so.
export function WorkNotice({ title, state, since, onShow }: Props) {
  const elapsed = useElapsed(state === "running" ? since : null);
  return (
    <div className="work-notice" data-state={state} role="status">
      <Icon name={state === "running" ? "spinner" : state === "ready" ? "check" : "alert"} size={14} className={state === "running" ? "spin" : undefined} />
      <p>
        {state === "running" ? (
          <>
            {title} is being worked on
            {elapsed && (
              <>
                <span className="work-notice-sep" aria-hidden="true">
                  {" · "}
                </span>
                <span className="elapsed">{elapsed}</span>
              </>
            )}
          </>
        ) : state === "ready" ? (
          `${title} is ready`
        ) : (
          `${title} did not finish`
        )}
        <span className="work-notice-sep" aria-hidden="true">
          {" · "}
        </span>
        <button type="button" className="button-link" onClick={onShow}>
          {state === "running" ? `Back to ${title}` : "Show it"}
        </button>
      </p>
    </div>
  );
}
