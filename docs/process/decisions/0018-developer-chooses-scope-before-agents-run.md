# 0018 The developer chooses the scope before an agent runs; fewer autonomous rounds

- Date: 2026-11-25
- Status: accepted (narrows point 2 of ADR 0017: Accept no longer starts Design and Tests, and tests are not run on their own)
- Decided by: Claude Code (Opus 5.5) as a subagent on branch `feature/slim-demo`, for the presentation on 2026-11-30

## Context

The presentation has a 12 minute slot with a live demo. A real build of an expense tracker on DeepSeek V4.1 Flash (2026-11-25) took about 25 minutes. Most of it went into agent rounds nobody asked for: the architect made five model calls with nine tool calls (about two minutes), the coder ten calls with 23 `check_python` and 4 `compare_with_design` calls (four minutes), the tester five calls with eleven `check_python` calls (almost four minutes), and one test seeded 10,000 expenses one call at a time, which pushed pytest over its 120 s limit. The developer: "the tool does too much by itself; we want to interact with it more, which is also better for the demo."

## Decision

1. **Design asks first.** The design step opens on a choice of diagram kinds (use case, class, sequence, activity, state, component, deployment; use case, class and sequence ticked) and a level, **simple** (key classes, at most one sequence for the main flow) or **detailed**. Both are fields of the design wing's `generate` input; the architect draws exactly the chosen kinds. Code reports kinds drawn without being chosen and kinds chosen but missing. A revision keeps the kinds of the current design and its level (stored per diagram as `content.level`, carried into the refined copy). The reviewer is told the choice and does not ask for other kinds. The approval rule (every functional requirement in a diagram) is unchanged.
2. **Tests ask first.** The tests step opens on **focused** (about one test per acceptance criterion) or **thorough**. The wing gives the tester a hard limit computed from the number of acceptance criteria (focused: criteria + 2, between 6 and 20; thorough: twice the criteria + 4, between 12 and 50) and refuses an answer with more tests, so the model retries with the count. The prompt forbids large data, sleeps and real servers unless a requirement is about serving pages. Writing again without a depth keeps the last one.
3. **Running the tests is the developer's click.** Tests are no longer run right after they are written; the step shows "The tests are written but have not run yet." and "Run the tests". The developer can read the tests first, and the run is a visible moment in the demo.
4. **Fewer tool rounds.** The tester gets no tools (every file is parsed when the answer is validated, and the real pytest run reports the rest). The coder keeps only `compare_with_design`, with at most two rounds. The architect may use two rounds at the simple level and four at the detailed level; the prompts ask for all checks in one round.
5. **What stays.** Every check that decides approval is still computed by code after the answer: PlantUML basics, consistency, coverage, parsing, drift against the class diagram, the real pytest run, the deployment check. Accept still starts the review, the code and the deployment at once; the change flow and catch-up still use `refresh_step` (Tests: write, then run).

The frontend reads the choices from the action's JSON schema (an `enum`, or an array of an `enum`; `default` is what is ticked; `option_hints` gives one line per option), so a wing that adds a choice to its generator gets the same screen without frontend code.

Rejected:

- **A free-text guidance box for the design scope.** The model would have to interpret it, and the demo cannot show what was chosen.
- **Dropping diagrams of kinds that were not chosen.** Could silently lose coverage; reporting the mismatch keeps the developer in charge.
- **A per-test timeout in pytest.** Needs a plugin beyond the standard library; the prompt rules and the cap address the cause.
- **Asking for test depth inside the text box.** Choices in a select next to the text box were easy to miss; they belong on the start screen.

## Consequences

- A build takes two more clicks (Draw the design, Write the tests) and one more (Run the tests) than before, each a visible decision.
- The CLI, MCP and catch-up get the slim defaults (use case, class, sequence; simple; focused) when they send no choice.
- A design without a class diagram has no drift check; the code is then checked only for parsing and by the tests. The UI says so in the hint of the class option.
- Not yet measured on a real model. Estimate for the expense tracker: design about 1 minute instead of 2, code 2 to 2.5 instead of 4, tests 1 to 1.5 instead of almost 4, plus a pytest run in seconds instead of a time-out.
