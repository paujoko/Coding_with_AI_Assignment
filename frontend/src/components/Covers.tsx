// The requirement IDs an artifact traces to, each a link to the requirement (it works while an agent works, too).
export function Covers({ ids, label = "Covers", onOpen }: { ids: string[]; label?: string; onOpen: (id: string) => void }) {
  if (ids.length === 0) return null;
  return (
    <p className="covers">
      <span className="trace-label">{label}</span>
      {ids.map((c) => (
        <button key={c} type="button" className="req-chip" onClick={() => onOpen(c)}>
          {c}
        </button>
      ))}
    </p>
  );
}
