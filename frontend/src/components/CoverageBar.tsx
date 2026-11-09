import type { Coverage } from "../api/types";

// Deterministic check from the backend: which requirements no diagram covers.
export function CoverageBar({ coverage }: { coverage: Coverage }) {
  const ids = [...Object.keys(coverage.covered), ...coverage.uncovered].sort();
  if (ids.length === 0) return null;
  return (
    <section className="coverage" aria-label="Requirement coverage">
      <p>
        {coverage.uncovered.length === 0
          ? `Every requirement appears in at least one diagram.`
          : `${coverage.uncovered.length} of ${ids.length} requirements appear in no diagram.`}
      </p>
      <div className="coverage-ids">
        {ids.map((id) => {
          const by = coverage.covered[id];
          return (
            <span key={id} className={`tag ${by ? "tag-ok" : "tag-missing"}`} title={by ? `In: ${by.join(", ")}` : "Not covered"}>
              {id}
            </span>
          );
        })}
      </div>
      {coverage.unknown_refs.length > 0 && (
        <p className="notice">Diagrams refer to requirements that do not exist: {coverage.unknown_refs.join(", ")}.</p>
      )}
    </section>
  );
}
