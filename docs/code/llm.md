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
