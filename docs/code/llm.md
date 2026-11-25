# LLM access

## One port, four providers

`application/ports.py: LLMClient.complete(LLMRequest) -> LLMReply`.

- `LLMRequest`: the calling agent's name, its system prompt, chat turns, a model `tier` (`small`, `mid`, `frontier`), `json_mode`, the offered `tools` and `tool_choice` (`auto`, or `none`: the tools stay defined but may not be called).
- `LLMReply`: text, the model that answered, token `usage`, `cost_usd` (None means unknown, never 0), `tool_calls`, and `provider_content`: the provider's own content blocks of that reply.
- `ChatTurn`: role `user`, `assistant` or `tool`; assistant turns carry `tool_calls` and `provider_content`, tool turns `tool_call_id`.

| Provider | Adapter | Key | Default models (small / mid / frontier) |
|---|---|---|---|
| `mock` (default) | `adapters/llm_mock.py: ScriptedLLM` | none | scripted |
| `openai` | `adapters/llm_openai.py: OpenAILLM` (chat completions) | `OPENAI_API_KEY` | `gpt-5-nano` / `gpt-5-mini` / `gpt-5` |
| `openrouter` | `adapters/llm_openrouter.py: OpenRouterLLM` (same wire format, reports cost) | `OPENROUTER_API_KEY` | `deepseek/deepseek-v4.1-flash-1017` on every tier (the only model the course's keys may use since 2026-11-09) |
| `anthropic` | `adapters/llm_anthropic.py: AnthropicLLM` (Messages API, official `anthropic` SDK) | `ANTHROPIC_API_KEY` | `claude-haiku-5-5` / `claude-sonnet-5-5` / `claude-sonnet-5-5` |

Choose with `WINGS_LLM_PROVIDER` or on the Settings page. Models per tier: `WINGS_MODEL_SMALL`, `WINGS_MODEL_MID`, `WINGS_MODEL_FRONTIER`. Claude only: `WINGS_EFFORT_SMALL|MID|FRONTIER` (`low`, `medium`, `high`, `xhigh`, `max`; unset: the model's default) and `ANTHROPIC_BASE_URL` (another endpoint that speaks the Messages API; unset: `api.anthropic.com`). `.env.example` lists them all.

**Rule:** AI coding agents never switch to a paid provider or call a real API, the Settings test button included. Humans do real runs. Adapters are tested with fake transports.

## Tiers per agent

The tier is set where each wing builds its agents (`phases/*/module.py`).

| Agent | Wing | Tier |
|---|---|---|
| analyst | requirements | mid |
| architect | design | frontier |
| reviewer, refiner | refinement | frontier |
| coder | codegen | mid |
| tester | testing | mid |
| debugger | testing | frontier |
| deployer | deployment | mid |
| impact_analyst | maintenance | mid |
| explainers (discussion answers) | every wing | mid, except design (frontier) |

`small` is used only by the Settings connection test today.

## Structured output

`application/structured.py: call_structured(llm, request, Schema)`:

1. Appends the JSON schema of `Schema` to the system prompt.
2. Extracts JSON from the reply (fenced block or the outermost braces).
3. Validates with Pydantic. On failure, sends the error back and asks for corrected JSON, up to two retries (s03: DeepSeek twice returned empty content; an empty reply gets its own message).
4. After the retries, raises `LLMOutputError` with a one-line reason a developer can read (`short_reason`: the field and the rule, no library text), the last raw reply and every reply. `LLMAgent` logs `agent.llm_failed` with the cost of the failed attempts, the orchestrator logs `phase.error`, and nothing is saved.

`extract_json` takes a reply that is JSON as a whole as it is; only otherwise it looks for a ```` ```json ```` fence or the outermost braces. Session s03 found the old order wrong: a `DEPLOY.md` with a ```` ```bash ```` block inside the JSON was taken for the answer.

Validators on the schemas are part of the contract with the model: `DiagramItem` rejects PlantUML without `@startuml`/`@enduml`, so the retry message tells the model exactly that.

**JSON mode is a capability of the endpoint, not a promise.** The steps above enforce the JSON for every provider. `json_mode` only adds the provider's own JSON switch where one exists:

- OpenAI and OpenRouter: `response_format: json_object`, only while no tools are offered (with both, DeepSeek V4.1 Flash never called a tool and answered with the tool's arguments, real run s03).
- `OpenAICompatibleLLM(json_mode=False)` never sends it. Use it for an endpoint that rejects it: Anthropic's OpenAI-compatible endpoint answered `json_object` with 400 (real run, 2026-11-25).
- Anthropic's Messages API has no JSON mode; `AnthropicLLM` sends none.

## Tools (tool calling)

- `ToolSpec` (name, description, JSON schema), `ToolCall` (id, name, arguments) and tool turns (`ChatTurn(role="tool", tool_call_id=...)`) are part of the port; `LLMRequest.tools` offers tools, `LLMReply.tool_calls` asks for them.
- `call_structured(..., run_tool=...)` loops: run the requested tools, send their results back, ask again. After `max_tool_rounds` (default 4) it sets `tool_choice="none"` and tells the model to answer; a tool call in a later reply is not run. Unknown tools and invalid arguments come back to the model as error text, never as a crash. A call repeated with the same arguments is not run again: the model gets the earlier result and is asked not to repeat it (s03: the tester re-checked unchanged files every round).
- Why `tool_choice="none"` instead of removing the tools: Claude checks that the tool list did not change under its earlier thinking blocks. The OpenAI-compatible adapters translate `none` into "send no tools and use JSON mode again", which is what they did before.
- Each assistant turn in the loop carries the reply's `provider_content`, so an adapter can send its own blocks back unchanged. A retry after invalid JSON drops them when the reply held tool calls that were not run (the API refuses a tool call without its result).
- `LLMAgent.ask(ctx, turns, Schema, tools=[...])` builds the specs, runs each call with the phase context, logs `agent.tool_call` (agent, tool, result) and then `agent.llm_call` with the number of calls.
- The mock plays scripted tool rounds from `"<agent>:tools"` (one list entry per round, `{"tool_calls": [{"name", "arguments"}]}`) while `tool_choice` is `auto`, then its normal answer; tool rounds do not count as conversation stages.
- Tools available today (`application/tools.py`): `check_python` (a file parses), `compare_with_design` (classes, public methods, inheritance and unambiguous attributes against all class diagrams, `domain/code.py`), `trace_impact` (what traces to given REQ ids and their latest test). Design tools: `check_plantuml` (basic checks plus PlantUML's own `-syntax` check through the renderer port, line numbers counted from 1), `check_consistency` (`domain/uml.py`: every sequence participant is a class, every called operation exists, inheritance and realisation followed), `check_coverage` (REQ ids not covered or unknown). The architect gets all three; the design wing runs the consistency check again by code and reports disagreements in the reply and in `data.consistency`.
- Who gets which tools: architect, reviewer and refiner the three design tools; coder `compare_with_design` (`CODE_TOOLS`); tester none; debugger `check_python`; impact analyst `trace_impact`. Since ADR 0018 a wing may pass a lower `max_tool_rounds` (architect: 2 simple, 4 detailed; coder: 2), because every round is a full model call; files that do not parse are refused by the output schemas anyway. Every check is also run by code after the answer, so a model that skips its tools cannot skip the check.

## The OpenAI-compatible adapters

- `OpenAILLM` and `OpenRouterLLM` share `OpenAICompatibleLLM` (`httpx`, `/chat/completions`, standard `tools` / `tool_calls` wire format).
- HTTP errors become `LLMError` with a hint for the common cases (401 wrong key, and an OpenRouter key `sk-or-...` saved as the OpenAI key; 402 and 403 credit or budget used up; 404 unknown model; 429 rate limit or no credit). One call may take up to 300 s (`TIMEOUT`; s03 had answers with many reasoning tokens).
- OpenRouter sends `usage: {include: true}` and reports `usage.cost`. For other endpoints the adapter looks the model up in `adapters/pricing.py`; OpenAI has no prices there, so its cost is unknown.

## The Anthropic adapter (ADR 0021)

- Official `anthropic` SDK (2.x, built on `httpx2`), `client.beta.messages.stream(...)` and `get_final_message()`. Every answer is streamed, so a long one (P4 Code took 318 s on Opus) never hits an HTTP timeout. `max_tokens` 64,000.
- Mapping: the system prompt goes to `system`; user turns become text blocks; assistant turns send `provider_content` back unchanged when it holds text or a tool call, else they are built from text and `tool_calls` as `tool_use` blocks; tool turns become `tool_result` blocks. Consecutive turns of one role are merged, so all results of one round go in one user message. Empty text blocks are never sent. A conversation that starts with an assistant turn gets a short user turn in front; one that ends on an assistant turn gets "Continue." (current Claude models refuse an assistant prefill).
- Why `provider_content`: with thinking on, Claude's thinking block must go back unchanged with the tool call it belongs to. The adapter keeps every block of the reply (`to_dict`), the application only carries it.
- No `thinking` parameter: the current models think adaptively by default, and an older model id typed in Settings cannot make the request invalid. `output_config.effort` is sent only for a tier with an effort set.
- Tools: `{name, description, input_schema}`; `tool_choice: {type: "none"}` for the last round.
- Refusals: on `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-fable-5-2`, `claude-fable-5-1` and `claude-opus-5` the request sets `fallbacks: "default"` with the beta `server-side-fallback-2026-07-01`: if a safety classifier declines, the API reruns the request on a fallback model inside the same call. After such a switch only the tool calls after the last `fallback` block count, and the declined model's thinking and tool calls are not sent back. A final `stop_reason: "refusal"` becomes `LLMError` with the category. Haiku has no server-side fallback.
- `stop_reason: "max_tokens"`: the text is kept (validation and the retry decide), tool calls are dropped, because a cut-off call is incomplete.
- Errors: the SDK retries 408, 409, 429, 5xx and 529 twice. What is left becomes `LLMError("Anthropic returned <status> (<hint>): <API message> [request <id>]")`, with hints for 400, 401 (and an OpenRouter key in the Anthropic field), 402, 403, 404, 413, 429, 5xx and 529 overloaded. Network failures and timeouts: "Anthropic request failed".
- The SDK sends the key as `Authorization: Bearer`, as SDK 2.x does for API keys.

## Usage and cost

- `usage` keeps `prompt_tokens` and `completion_tokens` for every provider. Anthropic's `input_tokens` excludes cached tokens, so the adapter adds cache reads and writes into `prompt_tokens` and also reports them as `cache_read_input_tokens` and `cache_creation_input_tokens` when they are not 0.
- `adapters/pricing.py: cost_usd(model, input, output, cache_read, cache_write)` prices a call from a small table: `claude-opus-5-5` $4 / $20, `claude-sonnet-5-5` $2 / $10, `claude-haiku-5-5` $0.10 / $0.50 (above 100K prompt tokens $0.50 / $2.50), `claude-fable-5-2` $8 / $40 per million input / output tokens, cache writes 1.25 x input, cache reads at the listed rate. Anthropic's first-party API rates as of 2026-11-03. A model that is not in the table, or a cache read without a known price, gives None.
- `agent.llm_call` and `agent.llm_failed` events carry model, attempts, seconds, `usage` and `cost_usd` summed over every call of the answer (tool rounds, retries). If any call's cost is unknown, the sum is None: a partial sum would look like the full price.
- The Activity view shows a second line under each model answer: "12,345 tokens in, 678 out, $0.0315", or "cost unknown", or "demo model, no cost" (`frontend/src/lib/cost.ts`).

## Settings page and configuration

- `config.py` reads `.env` at start (real environment variables win, so an `ANTHROPIC_API_KEY` set in the shell is used) and `write_env_file` keeps comments and other lines when the UI saves.
- `bootstrap.LLMSettings` backs `GET /api/settings`, `PUT /api/settings/llm` (`provider`, `api_key`, `models`, `efforts`) and `POST /api/settings/llm/test`: it writes `.env`, rebuilds the client and swaps `orchestrator.llm` without a restart. Keys are never sent back to the browser, only a hint (`sk-…1234`). An unknown effort is refused with 422.
- A paid provider without a key does not stop the app: `NotConfiguredLLM` answers every call with "paste the key in Settings", and `/health` reports `llm_ready: false` (the UI shows a banner).
- On the Settings page, Claude shows an effort choice next to each tier's model ("Effort: model default" or a level).

## The scripted mock

- Script file: JSON object, agent name -> list of replies (objects are serialized to JSON text). Plain chat calls use the key `<agent>:chat` if present.
- **Reply choice by conversation stage:** reply N answers a request that contains N earlier assistant turns; the last reply repeats. This is deterministic across processes (CLI and server behave alike) and a retry moves to the next reply.
- `demo_todo.json`: analyst asks three questions, then writes five requirements; architect returns use case, class and sequence diagrams; one canned discussion answer each.
- **Scenarios:** a key `<agent>?<phrase>` holds the replies for every request whose conversation contains the phrase (case ignored). The demo script has one, `?priority (high, normal or low`: the scripted change request "Tasks need a priority" puts that phrase into the requirements, and from then on analyst, architect, refiner, coder, tester and deployer answer with the version of their output that has the priority (Task.priority in the class diagram, in the code and the JSON file, four more tests that really pass, one more line in DEPLOY.md). So a change carried through the phases produces real differences on the mock. A second one exercises JavaScript tests (ADR 0020): "web view" in a request to the coder (for example Code, "Add a small web view of the list; keep its formatting in JavaScript.") gives `coder?web view`, the to-do code plus `todo/static/tasks.js` (exports `formatTask`, `listLines`), `page.js` (a page script without exports) and `index.html`; once the code contains `formatTask`, `tester?formattask` adds `tests/tasks.test.js` (two `node:test` tests for REQ-002) and declares REQ-002 as only partly testable because of `page.js`. When both phrases are present, the first matching key in the file wins (priority).
- The mock's cost is 0 and its model is `mock/<agent>`.
- **Delay:** `WINGS_MOCK_DELAY=<seconds>` (at most 60, default 0) makes the mock wait before every answer. It only serves to see the working screens in a browser (the sent message, "Working", the notice on other steps); the mock otherwise answers in milliseconds.
- Tests build their own scripts from it (`tests/conftest.py: make_orchestrator`).

## Tests

- `tests/adapters/test_llm_openai.py`: request shape, error hints, JSON mode left out with tools and with `tool_choice="none"`, an endpoint that rejects `json_object` (`httpx.MockTransport`).
- `tests/adapters/test_llm_anthropic.py`: a fake Messages API (`httpx2.MockTransport` answering with server-sent events) checks request mapping, streaming, effort, fallbacks, the tool round trip with thinking blocks, merged tool results, usage and cost, error hints, refusals and the base URL. No test reaches the real API.
- `tests/adapters/test_pricing.py`, `tests/application/test_tools.py` (cut-off with `tool_choice`, provider blocks carried, unknown cost stays unknown), `tests/test_settings.py` (Anthropic key, models and efforts in `.env`).

## The LLM log

- The real adapters log every request body and reply, and `LLMAgent` every tool call with its input and output, to the logger `wings.llm` at debug level.
- Only the server (`wings/main.py`) writes it to a file: `attach_llm_log` in `adapters/llm_log.py` puts it at `<workspace>/wings_llm.log` (default `workspaces/wings_llm.log`, or under `WINGS_WORKSPACE_DIR`), 10 MB per file, three older files. Tests, the CLI and the MCP server write no log file.
- It holds whole prompts, so it is runtime data: the workspace is git-ignored, and `.gitignore` also ignores `wings_llm.log*` at the root, where it was written before 2026-11-25.
- Read it before judging a model: it shows what Wings sent (ADR 0019 came from it).
