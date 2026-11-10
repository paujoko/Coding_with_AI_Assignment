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
| Versions | The new UI crashed on Paul's machine because the backend from session s01 was still running; the error page offered no way back. All tests and walks had used a fresh backend. | Paul, first local run | Frontend and backend are updated separately on a laptop. Version the API (`api_version`), tolerate missing fields, and never let an error page be a dead end. |
| Design judgement | Claude judged its first layout "clean"; the human found it too full and asked for familiar chat patterns. | Paul looking at it | An AI reviewing its own design applies its own taste. Ask the user early, and prefer patterns users already know over a new idea. |
| Web access | prompt-kit.com could not be fetched from the cloud container (DNS blocked), nor could the demo pages of the other libraries. | Web fetch errors | Open-source UI kits can be read from their GitHub repository instead; reading the components gave more exact patterns than the marketing pages would have. |
| Test environment | jsdom has no `Element.scrollTo`; the new auto-scroll crashed four component tests. | Vitest | Prefer the plain DOM property (`scrollTop`) that works in every environment. |
| Words | Status words ("Ready for review", "Out of date") told the developer what the system thinks, not what to do; the course's wing names were jargon to a user. | Paul could not tell how to proceed | Label steps with the action the user takes, use one vocabulary everywhere, keep project jargon as a second label. |
| Configuration | Real models needed environment variables set by hand; `.env` was documented but never read. | Paul asked to only paste a key | Read `.env` at start and let the UI write it; a missing key must explain itself instead of crashing. |
| Iterating vs rethinking | Two rounds polished the number line (labels, numbers, words) before the human asked to drop it; the list form fits the product better. | Paul | When feedback on the same element repeats, question the element, not its details. |
| Overlays | A floating help card covered the chat input; the scripted browser walk timed out clicking an answer. | Playwright walkthrough | Floating panels must not cover the primary task; put explanations where the empty space is, or in a dialog the user opens. |
| Libraries | The MCP SDK moved to 2.x and renamed `FastMCP` to `MCPServer`; code from memory (1.x) failed at import. | Import error with a migration hint | Check the installed version's API before writing against it; pin the major version (`mcp>=2.3,<3`). |
| Off-by-one | PlantUML's `-syntax` reports 0-based line numbers; the first implementation passed them through and pointed one line too early. | Real stdio run with the real jar | Test against the real tool once; a mocked subprocess repeats your own assumption. |
| Setup | Diagrams fell back to source on Paul's laptop with no hint why; the cloud container had PlantUML from apt, so it never showed there. | Paul's screenshot | A missing dependency must be fixable from where its absence shows. Test once without the optional tools installed. |
| Hidden field loss | The frontend API client builds the trace object field by field (defaults for old backends) and silently dropped the new `results` field; tests of the view passed because they build the object themselves. | Screenshot of the trace page without the test column | A normalizer that lists fields is a second place to update. Keep a test that goes through the client, or spread the response before applying defaults. |
| Two copies of the truth | After P3 made a refined copy of the design, impact lists and the trace named every diagram twice. | Screenshot of a change request | When data is copied on purpose, every reader must choose one copy; put that choice in one function (`without_superseded`). |
| Patching with sed | A sed replacement of a nested f-string did not match and left a cryptic `chr()` workaround in the code until a grep found it. | grep before commit | For multi-quote code, edit with a script that asserts the old text exists, then read the result. |
| Running generated code | Running model-written tests is necessary for honest results but runs untrusted code with the user's rights. | Design of P5 | Strip secrets from the environment, isolate the folder, set timeouts, and say plainly that this is not a security boundary (ADR 0013). |
| Copies and time | The refined copy of the design was preferred forever; a later change to P2 never reached code or tests. 170 tests passed, none changed P2 after a refinement. | Independent review | When two sources can hold the same thing, decide by recency or state, and write the test that changes the older source after the newer one exists. |
| Sandbox claims | "No secrets in the environment" was true for the child's variables, but the child could read the parent's through /proc and the key file on disk, and it shared the parent's stdin. | Review probes | Describe a sandbox by what an attacker can do, not by what you removed. Close stdin for child processes of a stdio server. |
| Lossy ids | Slugging paths for ids merged `__main__.py` and `main.py`; one file disappeared without an error. | Review probe | Any many-to-one mapping used as a key needs a collision check where the data enters. |
| Gates | Testing could be approved without a green run, although "results come from code" is a core rule. | Review | A rule that matters must be a gate in code, not only a convention in the UI. |

## 2026-11-09, session s03: first real model run

| Area | What happened | Found by | Lesson |
|---|---|---|---|
| Fake servers | 178 tests passed, including an end-to-end test against a fake OpenAI server, yet the first real run produced a design with the text "placeholder". The fake server called tools whenever they were offered; DeepSeek V4.1 Flash with `response_format: json_object` never did and wrote the tool's arguments as its answer. | First real run, then the raw exchanges logged in a copy of the project | A fake server tests our code, not the model's behaviour. One cheap real run per new model is worth more than another fake test; keep a way to log raw exchanges. |
| Model claims | Without a PlantUML renderer the reviewer wrote "all diagrams are syntactically valid"; one earlier diagram had broken lines (`\nt` instead of `\n\t`). | Reading the raw reply | A model reports what it was told, not what was checked. Wings should say plainly when a check could not run. |
| Key names | The course key was an OpenRouter key, stored under `OPENAI_API_KEY`; Wings chooses the endpoint by provider, so it would have gone to OpenAI. | Paul, reading the course e-mail | Name the provider by the key's prefix (`sk-or-`) in Settings, or warn when they do not match. |

## 2026-11-09, session s03, second round: Paul's own run

| Area | What happened | Found by | Lesson |
|---|---|---|---|
| Hidden platform | The analyst offered "web app (HTML/CSS/JS)" and "mobile app"; the coder could only write Python and silently wrote a terminal program. | Paul asking "hat er es nicht als html programmiert?" | Every agent must know what the system can build; a limit known only to one agent turns into silent deviation downstream. |
| Overclaimed verification | The trace showed a browser requirement as verified because a test with its id passed, although the tester wrote it was only partly testable. | Reading the tester's notes next to the trace | Verification must take the agents' own reservations into account; a test name is not a proof. |
| Real users click twice | A seven-minute step with no visible progress led to a second send; the backend queued it and ran it again. | Paul's run, events one second apart | Refuse instead of queue, show elapsed time, and let a reloaded page know that work is running. |
| Parsing order | Looking for a code fence before trying the reply as JSON broke on a DEPLOY.md that contained a fence. | The error's input value (`bash\n./run.sh build`) | Try the strict interpretation first; heuristics only as a fallback. |
| A fix with its own bug | The first version of the gap artifacts listed the requirement ids in `covers`, which would have counted them as trace links, the opposite of their meaning. | Claude re-reading its change against the trace rules, then a test | Data that marks a requirement as missing must not use the field that marks it as present. |
| Noise hides signal | 10 of 11 drift lines were private helpers; the one real difference was easy to miss. | The control run | A check that follows its own documented rule ("private helpers are details") on only one side produces noise that teaches people to ignore it. |
