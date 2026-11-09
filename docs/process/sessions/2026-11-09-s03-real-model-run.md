# Session 2026-11-09 s03: first real model run (OpenRouter, DeepSeek V4.1 Flash)

- **Who:** Paul (instructions, approval of paid calls), Claude Code with Opus 5.5 in the desktop app on Paul's Windows machine
- **When:** about 21:00 to 21:55 CET (UTC+1)
- **Commits:** at the end of the session, on Paul's request, merged into `main` (see `../timeline.md`)
- **Mode:** agentic. Claude ran the test suites, started the servers, drove a project through the HTTP API with a script, and logged raw model exchanges to find a bug.

## Goal

Check that the branch runs on Paul's Windows machine, then run Wings for real against the course's new model and fix what breaks.

## Human prompts (verbatim, key removed)

> Du prüfst, ob das Projekt Wings in diesem Ordner auf meinem Windows-Rechner läuft. [...] Keine echten Aufrufe an OpenAI oder andere bezahlte Modelle. [...] .env nie lesen, nicht ausgeben und nicht committen. Nichts committen oder pushen, ausser ich sage es ausdrücklich.

Paul then forwarded the course e-mail (OpenAI keys disabled for cost reasons; every project gets an OpenRouter key with a daily budget; the allowed model is `deepseek/deepseek-v4.1-flash-1017`, also for the Codex agent) and asked:

> In der Env steht der Key als unter OpenAI, aber ich habe erst gerade gesehen, dass der Key gar nicht für OpenAI ist, sondern für DeepSeek. [...] Kannst du über den API-Weg irgendwie herausfinden, was für Limite es gibt?

> Mach du es (reading the key from .env for the limits check)

> ok bitte, teste nun ob alles funktioniert somit gebe ich dir frei dass du bezahlte aufrufen machen darfst einfach im Rahmen, teste udn schaue was funktioniert udn was nciht, dann verbessere und dann werd eich es auch testen

The CLAUDE.md rule "no paid LLM calls by AI agents" was lifted by Paul for this session only.

## What was done

| Time (CET) | Step | By | Result |
|---|---|---|---|
| 21:05 | Read the code: provider choice is by `WINGS_LLM_PROVIDER`, not by the key; an OpenRouter key under `OPENAI_API_KEY` is sent to api.openai.com | Claude | Told Paul: set provider OpenRouter, the key, and DeepSeek for all three tiers (the OpenRouter defaults are `:free` models, not allowed) |
| 21:10 | `GET https://openrouter.ai/api/v1/key` with the key read from `.env` by a script that never prints it | Claude | Effective budget: workspace, 10 USD per day, reset 00:00 UTC; 1.38 USD already spent that day by other keys of the workspace, 0 by ours; key valid until 2027-02-04 |
| 21:25 | `git status`, branch up to date; backend install and pytest; frontend install, vitest, tsc | Claude | 178 backend tests, 23 frontend tests, typecheck clean; `/api/health` gives `api_version` 6; Java 17 found |
| 21:28 | Provider switched through `PUT /api/settings/llm` (writes `.env`), connection test | Claude | DeepSeek answered in 0.7 s |
| 21:30 | Run 1: one project driven through the API by a script | Claude | Requirements fine; design returned one diagram, notes "placeholder", rationale "(see final)", 10 of 11 requirements uncovered; reviewer summary "placeholder"; no tool call at all |
| 21:34 | Design step repeated in a copy of the project with every raw exchange logged | Claude | First reply was `{"covers": [...]}`: the arguments of `check_coverage` written as the answer. 0 tool calls with `response_format: json_object` plus tools in the same request |
| 21:36 | Same step with JSON mode left out while tools are offered | Claude | 8 tool calls in 4 rounds, then a complete answer (7 diagrams, full coverage) |
| 21:37 | Test first, then fix in `adapters/llm_openai.py` | Claude | 179 backend tests |
| 21:39 | Run 2 with the fix, all seven wings | Claude | Every wing ran and could be approved: 12 requirements, 9 diagrams, 8 review findings (3 applied), 8 code files, 49 passing tests covering all 12 requirements, deployment check passed, a change request with impact, consistency check clean. 11 minutes, about 0.08 USD |

## Decisions

- JSON mode (`response_format`) is sent only when no tools are offered. The JSON is still enforced by the schema in the prompt, Pydantic validation and the retry. Not an ADR: a wire detail of one adapter.

## Problems and how they were found

| Problem | Found by | Fix |
|---|---|---|
| With JSON mode and tools in one request, DeepSeek V4.1 Flash never called a tool and answered with tool arguments; after the retry it filled the schema with "placeholder". All 178 tests passed, because the fake servers in the tests behave like OpenAI | First real run, then raw exchanges logged in a copy of the project | JSON mode only without tools; test `test_json_mode_is_left_out_while_tools_are_offered` |
| A sequence diagram had lines starting with `t  ` (the model wrote `\nt` instead of `\n\t`) | Reading the raw response | Not fixed in code: PlantUML's own syntax check through `check_plantuml` catches this, but only when a renderer is configured. Without one, the reviewer even claimed "all diagrams are syntactically valid" |
| Design could be approved with 1 of 11 requirements covered | Run 1 | Not changed; open question whether coverage should gate approval like P5 and P6 |

## Verification

- Backend: 179 tests (1 new), frontend 23 tests, `tsc -b --noEmit` clean.
- Real run 2 through all seven wings on DeepSeek V4.1 Flash, see the table above.

## Numbers

| Agent | LLM calls | Tool calls | Seconds | Cost (USD) |
|---|---|---|---|---|
| analyst | 1 | 0 | 15 | 0.0008 |
| architect | 5 | 9 | 95 | 0.0094 |
| reviewer | 4 | 10 | 60 | 0.0105 |
| refiner | 5 | 7 | 87 | 0.0195 |
| coder | 5 | 11 | 184 | 0.0151 |
| tester | 5 | 8 | 164 | 0.0240 |
| deployer | 2 | 0 | 39 | 0.0023 |
| impact analyst | 2 | 2 | 7 | 0.0009 |
| **total run 2** | | | **661** | **0.0825** |

All paid calls of the session together cost about 0.11 USD.

## Diagram renderer (after Paul's "Ja, lade es")

- `POST /api/settings/diagrams/download` fetched plantuml 1.2025.4 (22.6 MB) from the official GitHub release into `tools/`; `/health` reports `renderer: true, mode: jar` (Java 17).
- All 18 diagrams of run 2 (design and refined copies) render.
- Counter-check on the broken diagrams from the logged design reply: `check_plantuml` now reports "Line 12: Syntax Error?" (the `t  ` line) and "Line 22" (a one-line note with a line break). Without the renderer the same check had said "no basic problems found".
- Browser check at 1440 px: the run 2 project shows every step done, the review findings, the consistency table and the rendered use case diagram.

## Open after this session

- Decide whether low requirement coverage should block approving the design.
- Long steps (codegen 3 min, testing 2.7 min, mostly reasoning tokens): consider a lower reasoning effort for some agents.
- The OpenRouter budget is shared by the workspace; ask the course whether it is per project or for everyone.
