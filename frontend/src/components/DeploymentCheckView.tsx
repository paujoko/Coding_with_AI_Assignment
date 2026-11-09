import type { Artifact } from "../api/types";
import { Icon } from "./Icon";

// P6: static checks of the deployment files and one real start of the program (the smoke run).
export function DeploymentCheckView({ check }: { check: Artifact }) {
  const c = check.content;
  const problems: string[] = c.problems ?? [];
  return (
    <section className="doc" aria-labelledby="check-heading">
      <header className="doc-head">
        <div>
          <h2 id="check-heading">Deployment check</h2>
          <p className="meta">Computed by code <span aria-hidden="true">·</span> run {check.revision}</p>
        </div>
      </header>
      <div className="verdict" data-ok={c.passed || undefined} role="status">
        <Icon name={c.passed ? "check" : "alert"} />
        <p>
          <strong>{c.passed ? "Ready to ship." : "Not ready yet."}</strong>{" "}
          {c.passed ? "The files only start what exists, and the program started and exited cleanly." : "See what failed below."}
        </p>
      </div>
      <ul className="checks" aria-label="Checks">
        <li data-outcome={problems.length === 0 ? "passed" : "failed"}>
          <span className="check-mark" aria-hidden="true">
            <Icon name={problems.length === 0 ? "check" : "close"} size={12} />
          </span>
          <span className="check-name">Dockerfile and scripts copy and start only files that exist</span>
        </li>
        {problems.map((p) => (
          <li key={p} data-outcome="failed" className="check-sub">
            <span className="check-detail">{p}</span>
          </li>
        ))}
        <li data-outcome={!c.ran ? "skipped" : c.exit_code === 0 ? "passed" : "failed"}>
          <span className="check-mark" aria-hidden="true">
            <Icon name={!c.ran ? "chevron" : c.exit_code === 0 ? "check" : "close"} size={12} />
          </span>
          <span className="check-name">
            Smoke run <code>{c.command || "none"}</code>
          </span>
          <span className="check-detail">
            {!c.ran ? "not possible here" : c.exit_code === 0 ? `exit code 0 in ${Number(c.seconds ?? 0).toFixed(1)} s` : `exit code ${c.exit_code}`}
          </span>
        </li>
        <li data-outcome="skipped">
          <span className="check-mark" aria-hidden="true">
            <Icon name="chevron" size={12} />
          </span>
          <span className="check-name">Docker build</span>
          <span className="check-detail">not run here; the commands are in DEPLOY.md</span>
        </li>
      </ul>
      {c.output && (
        <details className="console">
          <summary>Output of the smoke run</summary>
          <pre className="raw">{c.output}</pre>
        </details>
      )}
    </section>
  );
}
