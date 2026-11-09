# Lessons: failures, AI limits, surprises

Append-only. Each entry: date, phase or area, what happened, how it was found, what we learned. These feed the report's reflection ("where did the agents fail", "what would you do differently").

## 2026-11-09, foundation session (Claude Code building the skeleton)

**Mistakes the coding agent made and how they surfaced**

| Area | Mistake | Found by | Lesson |
|---|---|---|---|
| Mock LLM | Replayed its script with a per-process call counter, so every CLI command restarted at the first reply and the requirements flow looped on the clarifying questions. | Manual CLI smoke test (all unit tests were green) | Unit tests that build one object per test cannot catch state that should survive across processes. Smoke-test real entry points. |
| Frontend | A `useEffect` with an expression body returned a value that React treated as a cleanup function; the page went blank after creating a project. | Browser check, console error | Typecheck and component tests passed; only running the app showed it. Added an error boundary so such a crash shows a message. |
| Frontend | Monospace font ligatures drew PlantUML `->` as arrow glyphs in the source editor. | Screenshot review | Looks nice, but misleads anyone editing source. Visual review catches what tests cannot. |
| Frontend | Diagrams listed alphabetically ("Complete a task" before "Use cases"). | Screenshot review | Order carries meaning for the reader: goals, structure, behaviour, runtime. |
| Frontend | Stale design phase told the developer to "regenerate or approve", which was impossible while requirements were unapproved. | Clicking through the change scenario | Hints must be derived from the same rules the backend enforces. Added a test. |
| Frontend | `scrollIntoView` on the newest message scrolled the whole page down on load. | Screenshot after reload | Scroll the container, not the element. |
| Tooling | Vitest 2 bundles its own Vite 5; types clashed with Vite 6. | `tsc` | Check peer versions when combining build and test tools. |
| Frontend | Phase titles broke mid-word ("Requiremen ts") at narrow widths. | Screenshot review | `overflow-wrap: anywhere` is the wrong default for labels; hyphenate instead. |
| Backend and frontend | Twelve issues, among them a lost-update race that bypassed the approval gate, path traversal on Windows, reused requirement IDs and gate holes. All green tests and the browser walkthrough had missed them. | Independent review by a fresh subagent that saw the code but not the author's reasoning | The author (human or AI) tests what it thought of. A reviewer without the author's context finds the cases nobody thought of. Worth the 4.5 minutes every time a slice is finished. |

**About the approach**

- Writing the design and plan first made the build fast and coherent; the tightly coupled interfaces (domain, ports, orchestrator) would have been hard to split across independent agents.
- The same AI wrote the code and the first tests, so the tests shared its blind spots (concurrency, Windows paths, deletion). Separate reviewing from writing.
- Deterministic checks (coverage, gates) were easy to test; everything an LLM does in Wings is only exercised against canned replies so far. The real quality of requirements and diagrams is untested until a human runs real models.
