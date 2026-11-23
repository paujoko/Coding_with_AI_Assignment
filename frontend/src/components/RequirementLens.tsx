import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { Artifact, Mutant, PhaseState, RequirementItem, TestRun, Trace } from "../api/types";
import { VERDICT_LABEL } from "../api/types";
import { CheckedByCode } from "./CheckedByCode";
import { Icon } from "./Icon";

interface Props {
  projectId: string;
  requirementId: string;
  trace: Trace;
  phases: PhaseState[];
  canRender: boolean; // pictures of diagrams are set up
  busy: boolean; // links to the phases wait while an agent works
  onSelect: (id: string | null) => void; // another requirement, or null: back to the matrix
  onOpenRequirement: (id: string) => void;
  onOpenArtifact: (artifactId: string, phase: string) => void;
  loadArtifacts?: (phase: string) => Promise<Artifact[]>; // default: the API; tests pass their own
}

// The phases whose artifacts tell a requirement's story. Read with the existing artifact route, one call each.
const STORY_PHASES = ["requirements", "design", "refinement", "codegen", "testing"];

const KIND_LABEL: Record<string, string> = {
  use_case: "Use case diagram",
  class: "Class diagram",
  sequence: "Sequence diagram",
  activity: "Activity diagram",
  component: "Component diagram",
  deployment: "Deployment diagram",
  state: "State diagram",
};

const OUTCOME_LABEL: Record<string, string> = { passed: "Passed", failed: "Failed", error: "Error", skipped: "Skipped" };

const fileName = (a: Artifact) => String(a.content.path ?? a.path ?? a.title ?? a.id);
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const fold = (name: string) => name.replace(/_/g, "").toLowerCase(); // addTask and add_task are the same name

/** Class and operation names a PlantUML diagram shows: `class TaskService`, `+add_task(title)`, `A -> B: list_tasks()`. */
export function diagramNames(source: string): Set<string> {
  const names = new Set<string>();
  for (const m of source.matchAll(/\b(?:class|interface|enum|entity)\s+"?([A-Za-z_]\w*)/g)) names.add(fold(m[1]));
  for (const m of source.matchAll(/([A-Za-z_]\w*)\s*\(/g)) names.add(fold(m[1]));
  names.delete("");
  return names;
}

/** The lines (1-based) of a Python file that define a class or function the diagrams name. */
export function linesNamedInDiagrams(code: string, names: Set<string>): Set<number> {
  const marked = new Set<number>();
  if (names.size === 0) return marked;
  code.split("\n").forEach((line, i) => {
    const m = line.match(/^\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)/);
    if (m && names.has(fold(m[1]))) marked.add(i + 1);
  });
  return marked;
}

// The same picture, loading state and failure state as the design view, without the editor.
function DiagramPicture({ projectId, artifact, canRender }: { projectId: string; artifact: Artifact; canRender: boolean }) {
  const [broken, setBroken] = useState(false);
  const [drawn, setDrawn] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const img = useRef<HTMLImageElement>(null);
  const svg = api.svgUrl(projectId, artifact.id, artifact.revision) + (attempt ? `&try=${attempt}` : "");
  useEffect(() => {
    if (img.current?.complete && img.current.naturalWidth > 0) setDrawn(true);
  }, [svg]);

  if (canRender && !broken) {
    return (
      <a className="diagram-canvas" href={svg} target="_blank" rel="noreferrer" title="Open full size" data-loading={!drawn || undefined} aria-busy={!drawn}>
        {!drawn && (
          <span className="diagram-wait" role="status">
            <Icon name="spinner" size={14} className="spin" />
            Drawing the diagram
          </span>
        )}
        <img
          ref={img}
          src={svg}
          alt={`${artifact.title}, rendered from PlantUML`}
          onLoad={() => setDrawn(true)}
          onError={() => {
            setBroken(true);
            setDrawn(false);
          }}
        />
      </a>
    );
  }
  return (
    <div className="source">
      {broken ? (
        <p className="notice" role="alert">
          <Icon name="alert" size={14} />
          <span>The picture could not be drawn. The PlantUML source is below.</span>
          <button
            type="button"
            className="button"
            onClick={() => {
              setBroken(false);
              setAttempt((n) => n + 1);
            }}
          >
            <Icon name="refresh" size={14} />
            Try again
          </button>
        </p>
      ) : (
        <p className="notice notice-info" role="status">
          <Icon name="image" size={14} />
          <span>Pictures need PlantUML, which is not set up on this computer yet. The PlantUML source is below.</span>
        </p>
      )}
      <pre className="raw lens-source" tabIndex={0} aria-label={`PlantUML source of ${artifact.title}`}>
        {artifact.text}
      </pre>
    </div>
  );
}

function CodeFile(p: { file: Artifact; names: Set<string>; openLabel: string; busy: boolean; onOpen: () => void }) {
  const text = p.file.text ?? "";
  const lines = text.split("\n");
  const marked = useMemo(() => linesNamedInDiagrams(text, p.names), [text, p.names]);
  const name = fileName(p.file);
  return (
    <li className="lens-item">
      <div className="lens-item-head">
        <h3 className="file-path">{name}</h3>
        <button type="button" className="link" disabled={p.busy} onClick={p.onOpen}>
          {p.openLabel}
        </button>
      </div>
      {p.file.content.purpose && <p className="lens-purpose">{p.file.content.purpose}</p>}
      <details className="lens-code">
        <summary>
          Show the code <span className="lens-count">{plural(lines.length, "line")}{marked.size > 0 && `, ${marked.size} named in the diagrams`}</span>
        </summary>
        <pre className="listing" tabIndex={0} aria-label={`Contents of ${name}`}>
          <code>
            {lines.map((line, i) => (
              <span key={i} className="listing-line" data-mark={marked.has(i + 1) || undefined}>
                <span className="listing-no" aria-hidden="true">
                  {i + 1}
                </span>
                {line || " "}
                {"\n"}
              </span>
            ))}
          </code>
        </pre>
      </details>
    </li>
  );
}

// One requirement from its text through the diagrams and the code to its tests, on one page (criterion C5:
// "pick a requirement and show how it appears in the design and in the code"). Everything shown is read from
// the artifacts and the trace; nothing is asked of a model.
export function RequirementLens(p: Props) {
  const { trace, requirementId: id } = p;
  const [loaded, setLoaded] = useState<Artifact[] | null>(null);
  const page = useRef<HTMLElement>(null);
  const load = p.loadArtifacts ?? ((phase: string) => api.artifacts(p.projectId, phase));

  useEffect(() => {
    let stop = false;
    setLoaded(null);
    const wanted = STORY_PHASES.filter((ph) => p.phases.length === 0 || p.phases.some((x) => x.id === ph));
    Promise.all(wanted.map((ph) => load(ph).catch(() => [] as Artifact[]))).then((sets) => {
      if (!stop) setLoaded(sets.flat().filter((a) => !a.retired));
    });
    return () => {
      stop = true;
    };
  }, [p.projectId, trace]); // eslint-disable-line react-hooks/exhaustive-deps

  const ids = trace.requirements.map((r) => r.id);
  const at = ids.indexOf(id);
  const prev = at > 0 ? ids[at - 1] : null;
  const next = at >= 0 && at < ids.length - 1 ? ids[at + 1] : null;

  // Left and right arrow step through the requirements, unless the keys belong to a field or a code listing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || p.busy) return;
      const el = e.target as HTMLElement | null;
      if (el?.closest?.("input, textarea, select, pre, [contenteditable]")) return;
      if (e.key === "ArrowLeft" && prev) p.onSelect(prev);
      if (e.key === "ArrowRight" && next) p.onSelect(next);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prev, next, p.busy]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    page.current?.scrollTo?.({ top: 0 });
  }, [id]);

  const phaseTitle = (phase: string) => p.phases.find((x) => x.id === phase)?.title ?? phase;
  const byId = new Map((loaded ?? []).map((a) => [a.id, a]));
  const item = (loaded ?? [])
    .filter((a) => a.kind === "requirements")
    .flatMap((a) => (a.content.requirements ?? []) as RequirementItem[])
    .find((r) => r.id === id);
  const title = item?.title ?? trace.requirements.find((r) => r.id === id)?.title ?? id;

  // What covers the requirement, from the trace (which already leaves out diagrams a refined copy replaced).
  const covering = (trace.covered[id] ?? []).map((aid) => trace.artifacts.find((a) => a.id === aid)).filter((a) => a !== undefined);
  const of = (kind: string) => covering.filter((a) => a.kind === kind);
  const diagrams = of("diagram");
  const files = of("source_file");
  const testFiles = of("test_file");

  const names = useMemo(() => {
    const all = new Set<string>();
    for (const d of diagrams) for (const n of diagramNames(byId.get(d.id)?.text ?? "")) all.add(n);
    return all;
  }, [loaded, id]); // eslint-disable-line react-hooks/exhaustive-deps

  const report = (loaded ?? []).find((a) => a.kind === "test_report");
  const tests = ((report?.content.tests ?? []) as TestRun[]).filter((t) => t.requirement === id);
  const result = trace.results?.[id];
  const reportCurrent = Object.keys(trace.results ?? {}).length > 0;
  const caughtCount = trace.strength?.by_requirement?.[id] ?? 0;
  const strength = trace.strength ? (loaded ?? []).find((a) => a.kind === "test_strength") : undefined;
  const caught = ((strength?.content.mutants ?? []) as Mutant[]).filter((m) => m.outcome === "caught" && (m.requirements ?? []).includes(id));

  return (
    <section className="page lens" aria-labelledby="lens-heading" ref={page}>
      <nav className="lens-bar" aria-label="Requirements">
        <button type="button" className="button button-quiet" onClick={() => p.onSelect(null)}>
          <Icon name="undo" size={14} />
          All requirements
        </button>
        <div className="lens-step">
          <button type="button" className="button" disabled={!prev} title={prev ? `${prev} (left arrow key)` : undefined} onClick={() => prev && p.onSelect(prev)}>
            Previous
          </button>
          <span className="lens-pos" aria-live="polite">
            {at + 1} of {ids.length}
          </span>
          <button type="button" className="button" disabled={!next} title={next ? `${next} (right arrow key)` : undefined} onClick={() => next && p.onSelect(next)}>
            Next
            <Icon name="arrowRight" size={14} />
          </button>
        </div>
      </nav>

      <header className="lens-head">
        <h1 id="lens-heading">
          <span className="req-id">{id}</span> {title}
        </h1>
        <p className="lens-tags">
          {item && (
            <span className="tag" data-priority={item.priority}>
              {item.priority}
            </span>
          )}
          {item?.type === "non_functional" && <span className="tag">quality</span>}
          <span>
            {plural(diagrams.length, "diagram")}, {plural(files.length, "code file")}, {plural(testFiles.length, "test file")}
          </span>
          <CheckedByCode />
          <button type="button" className="link" disabled={p.busy} onClick={() => p.onOpenRequirement(id)}>
            Open in Requirements
          </button>
        </p>
        {item?.description && <p className="lede">{item.description}</p>}
        {item && item.acceptance_criteria.length > 0 && (
          <ul className="criteria" aria-label="Acceptance criteria">
            {item.acceptance_criteria.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        )}
      </header>

      {loaded === null ? (
        <p className="empty-note" role="status">
          <Icon name="spinner" size={14} className="spin" /> Loading design, code and tests
        </p>
      ) : (
        <>
          <section className="lens-part" aria-labelledby="lens-design">
            <h2 id="lens-design">In the design</h2>
            {diagrams.length === 0 ? (
              <p className="trace-missing">No diagram covers this requirement.</p>
            ) : (
              <ul className="lens-items">
                {diagrams.map((d) => {
                  const a = byId.get(d.id);
                  return (
                    <li key={d.id} className="lens-item">
                      <div className="lens-item-head">
                        <h3>
                          {d.title}
                          {a && <span className="lens-kind">{KIND_LABEL[a.content.kind] ?? a.content.kind}</span>}
                        </h3>
                        <button type="button" className="link" disabled={p.busy} onClick={() => p.onOpenArtifact(d.id, d.phase)}>
                          Open in {phaseTitle(d.phase)}
                        </button>
                      </div>
                      {a ? <DiagramPicture key={`${a.id}-${a.revision}`} projectId={p.projectId} artifact={a} canRender={p.canRender} /> : <p className="empty-note">This diagram could not be loaded.</p>}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="lens-part" aria-labelledby="lens-code">
            <h2 id="lens-code">In the code</h2>
            {files.length === 0 ? (
              <p className="trace-missing">No code file implements this requirement yet.</p>
            ) : (
              <ul className="lens-items">
                {files.map((f) => {
                  const a = byId.get(f.id);
                  return a ? (
                    <CodeFile key={f.id} file={a} names={names} openLabel={`Open in ${phaseTitle(f.phase)}`} busy={p.busy} onOpen={() => p.onOpenArtifact(f.id, f.phase)} />
                  ) : (
                    <li key={f.id} className="lens-item">
                      <h3 className="file-path">{f.title}</h3>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="lens-part" aria-labelledby="lens-tests">
            <h2 id="lens-tests">
              In the tests
              {result && (
                <span className="outcome" data-outcome={result}>
                  {VERDICT_LABEL[result] ?? result}
                </span>
              )}
            </h2>
            {testFiles.length === 0 && tests.length === 0 ? (
              <p className="trace-missing">No test checks this requirement yet.</p>
            ) : (
              <>
                {testFiles.length > 0 && (
                  <p className="lens-files">
                    {testFiles.map((f) => (
                      <button key={f.id} type="button" className="link file-path" disabled={p.busy} title={`Open in ${phaseTitle(f.phase)}`} onClick={() => p.onOpenArtifact(f.id, f.phase)}>
                        {f.title}
                      </button>
                    ))}
                  </p>
                )}
                {tests.length > 0 && !reportCurrent && (
                  <p className="notice lens-old" role="status">
                    <Icon name="alert" size={14} />
                    <span>The code or the tests changed after the last run. These results are from before.</span>
                  </p>
                )}
                {tests.length > 0 ? (
                  <ul className="checks" aria-label={`Tests of ${id}, latest run`}>
                    {tests.map((t) => (
                      <li key={`${t.classname}.${t.name}`} data-outcome={t.outcome}>
                        <span className="check-mark" aria-hidden="true">
                          <Icon name={t.outcome === "passed" ? "check" : t.outcome === "skipped" ? "chevron" : "close"} size={12} />
                        </span>
                        <span className="sr-only">{OUTCOME_LABEL[t.outcome] ?? t.outcome}: </span>
                        <span className="check-name">{t.name}</span>
                        {t.message && t.outcome !== "passed" && <span className="check-detail">{t.message.split("\n")[0]}</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-note">The tests have not been run yet.</p>
                )}
                {trace.strength && (
                  <div className="lens-bugs">
                    <p>
                      <strong>{caughtCount === 0 ? "No injected bug" : plural(caughtCount, "injected bug")} caught by these tests.</strong>{" "}
                      {caughtCount === 0
                        ? "Wings put small bugs into the code, one at a time; none of them made a test of this requirement fail. They may sit in code this requirement does not use."
                        : `Wings put small bugs into the code, one at a time; each one counted here made a test of ${id} fail.`}{" "}
                      <CheckedByCode />
                    </p>
                    {caught.length > 0 && (
                      <ul aria-label={`Injected bugs caught by the tests of ${id}`}>
                        {caught.map((m) => (
                          <li key={m.id}>
                            <span className="file-path">
                              {m.path} line {m.line}
                            </span>{" "}
                            {m.description}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </>
            )}
          </section>
        </>
      )}
    </section>
  );
}
