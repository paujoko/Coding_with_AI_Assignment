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

## 2026-11-09, session s02 (UI redesign in a cloud session)

| Area | What happened | Found by | Lesson |
|---|---|---|---|
| Requirements IDs | A revise through the mock returned requirements without IDs; all five were renumbered and every diagram link broke (trace 0 of 5). 79 green tests had not covered "revise without IDs". | Clicking the change scenario in the browser and reading the trace view | The mock replays what real models also do (drop fields). Test the unhappy shape of LLM output, not only the scripted happy one. Showing the trace in the UI made the bug visible at once. |
| Diagrams | Every class and use case diagram showed "Cannot find Graphviz" in the old UI; PlantUML returns that as a valid SVG, so the backend passed it on. | First screenshot of the old UI | A tool that reports errors inside a successful result needs an explicit check. |
| Logo | The first sketch (seven strokes fanning from the bottom) read as a sunburst, not as wings. | Rendering it at 16 to 256 px and looking | Sketch symbols at real sizes before committing; a meaning on paper is not a reading on screen. |
| Tooling | The requested design skill was not installed in the cloud environment; running a jar downloaded from the internet was blocked by the session's safety check. | Tool errors | Install tools from package managers (PlantUML and Graphviz came from apt); treat skills as guidance that can be read even when the tool is missing. |
| Old UI | Agent replies looked like text inputs, every heading had an eyebrow label, the log showed raw event kinds. Tests passed. | Screenshot review | Usability problems are invisible to unit tests; look at the screen. |
| Frontend state | The redesign added new ways to navigate (trace links) but kept the old "disable navigation while busy" guard only on the old ones; slow responses could also paint the wrong phase. | Independent review with delayed network responses in Playwright | Guards that depend on remembering every entry point break when the UI grows. Drop stale responses at the one place data arrives instead. Delaying responses on purpose is a cheap way to find races. |
