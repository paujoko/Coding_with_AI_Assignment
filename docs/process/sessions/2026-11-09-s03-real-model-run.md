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

## Second round: Paul's own run and everything it uncovered

Paul ran a project himself in the app on DeepSeek ("tik tak toe app", answered "web app in the browser", one human against the computer, board 3x3 to 5x5). It went through P1 to P5 and broke in P6 three times. Prompts (verbatim):

> es ist gerade bei testing udn alles ist blockeirt [...]

> ist das normal das das so lange dauert

> was ist heir pasiert

> ok wenn cih bescaheid sage und ich fetig bin dann amche zusätzlich zu dem was du eh shcon geplant hast noch all das, zusätzlich schickt es die nachricht nicht ab wenn man auf senden drückt also sie geht nicht weg und ist imemr ncoh da, fixe das auch [...]

> hat er es nciht als html oder so programmiert?

> ok gut du musst jetzt meinen test nicht mehr beanchten, aber schue ihn dir an ich glaube er hat viele fehler aufgedeckt, udn verbessere alles kannst den server gerne stoppen oder neu starten oder was auch immer, überlege zuerst gnaz gneau dann setzte um

### What the run showed (read from its events, messages and artifacts)

| # | Seen | Cause | Fix (test first) |
|---|---|---|---|
| 1 | Requirements for a browser game (REQ-015 "runs entirely in the browser with HTML/CSS/JS", must); the code was a terminal program; nobody said so | the coder prompt said "Python, standard library only"; analyst and architect did not know | one target platform in every prompt (Python CLI, or a local web app served by `http.server`); the coder may write `.html`, `.css`, `.js`, `.svg`; `deviations` (ADR 0014) |
| 2 | REQ-015 shown as verified although the tester wrote it could only partly be tested | "verified" meant only "a test named `req_015` passed" | tester `gaps`, coder `deviations` as `known_gaps` artifacts; `apply_gaps` gives `partial` or `not_met`; only `passed` counts |
| 3 | Deployment: `printf '0 0\nq\n' \| python -m tictactoe` refused | the smoke run had no way to give an interactive program input | `smoke_input` fed as standard input; pipes refused with a message that names `smoke_input` |
| 4 | Deployment: "expected value at line 1 column 1", input `bash\n./run.sh build` | `extract_json` searched for a code fence first and found the ```` ```bash ```` block inside `DEPLOY.md` inside the JSON | a reply that is JSON as a whole is taken as it is |
| 5 | Deployment: empty reply twice ("EOF while parsing") | DeepSeek returned empty content; not reproduced, cause unconfirmed | two retries instead of one, a specific message for empty replies |
| 6 | Errors shown as raw Pydantic text with a URL | the exception text went straight to the UI | one line: agent, attempts, field and rule |
| 7 | "Write tests" ran twice (6.7 + 5.6 min, 0.07 USD) | a second request waited on the project lock and then ran; after a page reload the UI did not know an agent was working | a second action is refused with 409; `running` in the project; the UI waits with a notice (API version 7) |
| 8 | The message stayed in the input box while the agent worked | the composer cleared only after the whole action | cleared at once, put back on failure |
| 9 | The tester's step took 6.7 minutes, checking the same files every round | identical tool calls were run again | repeated calls answered from memory with a note; elapsed time shown while an agent works |
| 10 | Costs of failed attempts missing, token counts too low | only the last reply of an answer was counted, failures not at all | sums over all calls; `agent.llm_failed` with cost |
| 11 | A single call may only take 180 s | adapter timeout | 300 s |
| 12 | (from run 1) a design covering 1 of 11 requirements could be approved | no gate | P2 approval needs every functional requirement in a diagram |
| 13 | Default OpenRouter models were `:free` models the course does not allow; an OpenRouter key saved as the OpenAI key gave no hint | defaults from the lecture; generic 401 text | DeepSeek V4.1 Flash as default on every tier; 401 hint for `sk-or-` keys; 402 and 403 budget hints |

Found while checking the fixes with a second real run:

| 14 | The consistency check listed 11 differences between design and code; 10 were private helpers (`-_serve_static()` in the diagram, a `_BoundHandler` class in the code) | the drift check ignored private methods in the code only | private names ignored on both sides; the real run now shows the one real difference (`log_message()` in the code only) |

### Verification

- Backend 199 tests (21 new), frontend 25 tests (2 new), `tsc` clean, production build.
- Browser: while the control run worked, a fresh tab on the same project showed "Start in Requirements is still running ... sending it again is not needed", a running clock (0:03) and a disabled send button; a second action sent by hand got 409 with "An agent is already working on this project (Answer in requirements, since 22:36:29 UTC)". The code view lists the web files. No console errors in a fresh tab. Screenshots of the phone and dark layouts were not possible this time (the browser pane was not on screen); the busy notice was seen at phone width in dark mode.
- Control run on DeepSeek with Paul's scenario (project `tic-tac-toe-web`): the analyst offered only buildable platforms; the result is a web app (Python `http.server`, `index.html`, `app.js`, `style.css`, 14 files); 107 tests pass; 11 of 12 requirements verified, REQ-012 ("clear, usable board", could) has no test and is shown as such; the smoke run `python -m tictactoe --check` passed; a maintenance change and the consistency check ran. 11 minutes, 0.107 USD, 424k tokens, 54 tool calls, no failed answer.

### Still open

- The tester declared no gap for REQ-012 although it wrote no test for it; Wings shows "no test", not "verified", but the declaration depends on the model.
- JavaScript in web pages is neither checked against the design nor tested.
- The drift check still ignores attributes and associations.
- Long steps (design about 2 min, code and tests about 2 to 3 min each on DeepSeek) are a demo risk; a lower reasoning effort was not tried.
