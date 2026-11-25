import { useState } from "react";
import type { Artifact, PhaseState, Trace } from "../api/types";
import { VERDICT_LABEL } from "../api/types";
import { CheckedByCode } from "./CheckedByCode";
import { Icon } from "./Icon";
import { RequirementLens } from "./RequirementLens";

interface Props {
  trace: Trace | null;
  phases: PhaseState[];
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase: string) => void;
  projectId?: string; // needed to load and draw what the requirement view shows
  canRender?: boolean; // pictures of diagrams are set up
  requirement?: string | null; // the requirement whose story is open; kept by the app so it survives a visit to a phase
  onRequirement?: (id: string | null) => void;
  loadArtifacts?: (phase: string) => Promise<Artifact[]>;
}

const TRACED = new Set(["diagram", "source_file", "test_file"]);

// Requirement x artifact matrix. Computed by the backend from the trace IDs, never by an LLM.
export function TraceView({ trace, phases, onOpenRequirement, onOpenArtifact, projectId = "", canRender = false, requirement, onRequirement, loadArtifacts }: Props) {
  const [own, setOwn] = useState<string | null>(null); // used when the app does not keep the selection
  const selected = requirement !== undefined ? requirement : own;
  const select = (id: string | null) => (onRequirement ? onRequirement(id) : setOwn(id));
  if (!trace || trace.requirements.length === 0) {
    return (
      <section className="page">
        <header className="page-head">
          <h1>Traceability</h1>
        </header>
        <p className="empty-note">Nothing to trace yet. Write the requirements first.</p>
      </section>
    );
  }
  if (selected && trace.requirements.some((r) => r.id === selected)) {
    return (
      <RequirementLens
        projectId={projectId}
        requirementId={selected}
        trace={trace}
        phases={phases}
        canRender={canRender}
        onSelect={select}
        onOpenRequirement={onOpenRequirement}
        onOpenArtifact={onOpenArtifact}
        loadArtifacts={loadArtifacts}
      />
    );
  }
  const phaseTitle = (id: string) => phases.find((p) => p.id === id)?.title ?? id;
  const total = trace.requirements.length;
  const covered = total - trace.uncovered.length;
  // Columns: what implements a requirement (diagrams, code, tests), grouped by the phase that made it.
  const order = phases.map((p) => p.id);
  const columns = trace.artifacts
    .filter((a) => TRACED.has(a.kind) && (a.kind === "diagram" || a.covers.length > 0)) // a file that traces to nothing adds an empty column
    .sort((a, b) => order.indexOf(a.phase) - order.indexOf(b.phase));
  const groups = columns.reduce<{ phase: string; span: number }[]>((acc, a) => {
    const last = acc.at(-1);
    if (last?.phase === a.phase) last.span += 1;
    else acc.push({ phase: a.phase, span: 1 });
    return acc;
  }, []);
  const results = trace.results ?? {};
  const ran = Object.keys(results).length > 0;
  const verified = trace.requirements.filter((r) => results[r.id] === "passed").length;
  // Injected bugs (P5 probe): only while the check is newer than code and tests; older backends send nothing.
  const strength = trace.strength ?? null;
  const caughtBy = strength?.by_requirement ?? {};
  const judged = strength ? Number(strength.caught ?? 0) + Number(strength.survived ?? 0) : 0;

  return (
    <section className="page" aria-labelledby="trace-heading">
      <header className="page-head">
        <h1 id="trace-heading">Traceability</h1>
        <p className="lede">
          {covered} of {total} requirements appear in at least one artifact
          {ran ? `, ${verified} are verified by passing tests` : ""}.
          {strength && judged > 0 ? ` The tests caught ${strength.caught} of ${judged} injected bugs.` : ""}{" "}
          <CheckedByCode />
        </p>
      </header>
      {trace.unknown_refs.length > 0 && (
        <p className="notice" role="status">
          <Icon name="alert" size={14} /> Artifacts refer to requirements that do not exist: {trace.unknown_refs.join(", ")}.
        </p>
      )}
      {columns.length === 0 ? (
        <p className="empty-note">Nothing traces to the requirements yet. Approve them and generate the design.</p>
      ) : (
        <div className="matrix-wrap">
          <table className="matrix">
            <thead>
              <tr className="matrix-groups">
                <td />
                {ran && <td />}
                {groups.map((g) => (
                  <th key={g.phase} scope="colgroup" colSpan={g.span}>
                    {phaseTitle(g.phase)}
                  </th>
                ))}
              </tr>
              <tr>
                <th scope="col" className="matrix-corner">
                  Requirement
                </th>
                {ran && (
                  <th scope="col" className="matrix-col matrix-result">
                    Latest test
                  </th>
                )}
                {columns.map((a) => (
                  <th key={a.id} scope="col" className="matrix-col">
                    <button type="button" className="link" title={a.title} onClick={() => onOpenArtifact(a.id, a.phase)}>
                      {a.kind === "diagram" ? a.title : a.title.split("/").pop()}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trace.requirements.map((r) => {
                const by = new Set(trace.covered[r.id] ?? []);
                return (
                  <tr key={r.id} data-uncovered={by.size === 0 || undefined}>
                    <th scope="row">
                      <button type="button" className="matrix-req" title={`Follow ${r.id} through design, code and tests`} onClick={() => select(r.id)}>
                        <span className="req-id">{r.id}</span>
                        <span>{r.title}</span>
                        <Icon name="chevron" size={12} />
                      </button>
                    </th>
                    {ran && (
                      <td className="matrix-result">
                        <span className="outcome" data-outcome={results[r.id] ?? "none"}>
                          {results[r.id] ? (VERDICT_LABEL[results[r.id]] ?? results[r.id]) : "no test"}
                        </span>
                        {caughtBy[r.id] > 0 && (
                          <span
                            className="matrix-caught"
                            title={`Wings put small bugs into the code, one at a time. ${caughtBy[r.id]} of them made a test of ${r.id} fail. Checked by code.`}
                          >
                            {caughtBy[r.id]} {caughtBy[r.id] === 1 ? "bug" : "bugs"} caught
                          </span>
                        )}
                      </td>
                    )}
                    {columns.map((a) => (
                      <td key={a.id}>
                        {by.has(a.id) ? (
                          <span className="hit" role="img" aria-label={`${r.id} in ${a.title}`} />
                        ) : (
                          <span className="sr-only">not in {a.title}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
