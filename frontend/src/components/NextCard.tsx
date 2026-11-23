import type { IconName } from "./Icon";
import type { ActId, NextAct, NextCard as Card } from "../lib/next";
import { CheckedByCode } from "./CheckedByCode";
import { Icon } from "./Icon";

const PRIMARY_ICON: Partial<Record<ActId, IconName>> = {
  approve: "check",
  approve_change: "check",
  keep_yes: "check",
  update: "refresh",
  update_one: "refresh",
  advance_change: "refresh",
  rerun: "refresh",
  go: "arrowRight",
};

// The one next step above the input: a status line, one primary button, quiet choices beside it.
// Tone "must" (amber or rust, with an icon) is what the developer has to read now; "info" is the way on.
export function NextCard({ card, busy, onAct }: { card: Card; busy: boolean; onAct: (act: NextAct) => void }) {
  const off = (a: NextAct) => a.disabled ?? (a.id === "stop" ? false : busy);
  const icon = PRIMARY_ICON[card.primary?.id ?? "start"];
  return (
    <div className="next" data-status={card.status} data-tone={card.tone} data-kind={card.kind} role={card.tone === "must" ? "alert" : "status"}>
      <Icon name={card.icon} className={card.status === "running" ? "spin" : undefined} />
      <p>
        <strong>{card.lead}</strong> {card.text}
        {card.byCode && (
          <>
            {" "}
            <CheckedByCode />
          </>
        )}
      </p>
      <div className="next-actions">
        {card.secondary.map((a) => (
          <button key={a.id + (a.phase ?? "")} type="button" className="link next-link" title={a.hint} disabled={off(a)} onClick={() => onAct(a)}>
            {a.label}
          </button>
        ))}
        {card.primary && (
          <button type="button" className="button button-primary" title={card.primary.hint} disabled={off(card.primary)} onClick={() => onAct(card.primary!)}>
            {icon && icon !== "arrowRight" && <Icon name={icon} size={14} />}
            {card.primary.label}
            {icon === "arrowRight" && <Icon name="arrowRight" size={14} />}
          </button>
        )}
      </div>
    </div>
  );
}
