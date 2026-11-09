// The requirement IDs an artifact traces to, each a link to the requirement.
export function Covers({ ids, label = "Covers", busy, onOpen }: { ids: string[]; label?: string; busy: boolean; onOpen: (id: string) => void }) {
  if (ids.length === 0) return null;
  return (
    <p className="covers">
      <span className="trace-label">{label}</span>
      {ids.map((c) => (
        <button key={c} type="button" className="req-chip" disabled={busy} onClick={() => onOpen(c)}>
          {c}
        </button>
      ))}
    </p>
  );
}
