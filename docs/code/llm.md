# LLM access

## One port, two adapters

`application/ports.py: LLMClient.complete(LLMRequest) -> LLMReply`. `LLMRequest` carries the calling agent's name, its system prompt, chat turns, a model `tier` (`small`, `mid`, `frontier`) and `json_mode`.

| Provider | Adapter | When |
|---|---|---|
| `mock` (default) | `adapters/llm_mock.py: ScriptedLLM` | tests, demos without a key, every AI coding agent |
| `openrouter` | `adapters/llm_openrouter.py: OpenRouterLLM` | real runs, started by a human |

Choose with `WINGS_LLM_PROVIDER`. Models per tier: `WINGS_MODEL_SMALL`, `WINGS_MODEL_MID`, `WINGS_MODEL_FRONTIER` (defaults in `config.py` are the free models named in the hands-on lecture; their exact OpenRouter IDs are unverified, check https://openrouter.ai/models).

**Rule:** AI coding agents never switch to a paid provider or call a real API. Humans do real runs.

## Structured output

`application/structured.py: call_structured(llm, request, Schema)`:

1. Appends the JSON schema of `Schema` to the system prompt.
2. Extracts JSON from the reply (fenced block or the outermost braces).
3. Validates with Pydantic. On failure, sends the error back once and asks for corrected JSON.
4. After the retry, raises `LLMOutputError` with the raw reply; the orchestrator logs `phase.error` and nothing is saved.

Validators on the schemas are part of the contract with the model: `DiagramItem` rejects PlantUML without `@startuml`/`@enduml`, so the retry message tells the model exactly that.

## The scripted mock

- Script file: JSON object, agent name -> list of replies (objects are serialized to JSON text). Plain chat calls use the key `<agent>:chat` if present.
- **Reply choice by conversation stage:** reply N answers a request that contains N earlier assistant turns; the last reply repeats. This is deterministic across processes (CLI and server behave alike) and a retry moves to the next reply.
- `demo_todo.json`: analyst asks three questions, then writes five requirements; architect returns use case, class and sequence diagrams; one canned discussion answer each.
- Tests build their own scripts from it (`tests/conftest.py: make_orchestrator`).

## Tiers per agent (current)

| Agent | Wing | Tier | Why |
|---|---|---|---|
| analyst | requirements | mid | asking good questions matters more than raw reasoning |
| architect | design | frontier | consistency across several diagrams is the hardest task so far |

## Providers and the Settings page (session s02)

| Provider | Adapter | Key |
|---|---|---|
| `mock` (default) | `adapters/llm_mock.py: ScriptedLLM` | none |
| `openai` | `adapters/llm_openai.py: OpenAILLM` (chat completions, JSON mode) | `OPENAI_API_KEY` |
| `openrouter` | `adapters/llm_openrouter.py: OpenRouterLLM` (same wire format, plus cost reporting) | `OPENROUTER_API_KEY` |

- Both real adapters share `OpenAICompatibleLLM`. HTTP errors become `LLMError` with a hint for the common cases (401 wrong key, 404 unknown model, 429 rate limit or no credit).
- A paid provider without a key does not stop the app: `NotConfiguredLLM` answers every call with "paste the key in Settings", and `/health` reports `llm_ready: false` (the UI shows a banner).
- `config.py` reads `.env` at start (real environment variables win) and `write_env_file` keeps comments and other lines when the UI saves.
- `bootstrap.LLMSettings` backs `GET /api/settings`, `PUT /api/settings/llm` and `POST /api/settings/llm/test`: it writes `.env`, rebuilds the client and swaps `orchestrator.llm` without a restart. Keys are never sent back to the browser, only a hint (`sk-…1234`).
- Default models per tier for OpenAI: `gpt-5-nano`, `gpt-5-mini`, `gpt-5`; editable in Settings. Coding agents never run the test button or real calls (CLAUDE.md); adapters are tested with `httpx.MockTransport`.

## Tools (tool calling)

- `ToolSpec` (name, description, JSON schema), `ToolCall` (id, name, arguments) and tool turns (`ChatTurn(role="tool", tool_call_id=...)`) are part of the LLM port; `LLMRequest.tools` offers tools, `LLMReply.tool_calls` asks for them.
- `call_structured(..., run_tool=...)` loops: run the requested tools, send their results back, ask again; after `max_tool_rounds` (default 4) the tools are withdrawn and the model is told to answer. Unknown tools and invalid arguments come back to the model as error text, never as a crash.
- `LLMAgent.ask(ctx, turns, Schema, tools=[...])` builds the specs, runs each call with the phase context, logs `agent.tool_call` (agent, tool, result) and then `agent.llm_call` with the number of calls.
- OpenAI and OpenRouter: standard `tools` / `tool_calls` wire format. `response_format: json_object` is sent only when no tools are offered: with both in one request DeepSeek V4.1 Flash never called a tool and answered with the tool's arguments (real run, session s03). The JSON is still enforced by the schema in the prompt, validation and the retry; the final answer after the tools are withdrawn uses JSON mode again. The mock plays scripted tool rounds from `"<agent>:tools"` (one list entry per round, `{"tool_calls": [{"name", "arguments"}]}`) before its normal answer; tool rounds do not count as conversation stages.
- Tools available today (`application/tools.py`): `check_python` (a file parses), `compare_with_design` (classes and public methods against the class diagram, `domain/code.py`), `trace_impact` (what traces to given REQ ids and their latest test). Design tools: `check_plantuml` (basic checks plus PlantUML's own `-syntax` check through the renderer port, line numbers counted from 1), `check_consistency` (`domain/uml.py`: every sequence participant is a class, every called operation exists, inheritance and realisation followed), `check_coverage` (REQ ids not covered or unknown). The architect gets all three; the design wing runs the consistency check again by code and reports disagreements in the reply and in `data.consistency`.
- Who gets which tools: architect, reviewer and refiner the three design tools; coder `check_python` and `compare_with_design`; tester and debugger `check_python`; impact analyst `trace_impact`. Every check is also run by code after the answer, so a model that skips its tools cannot skip the check.
