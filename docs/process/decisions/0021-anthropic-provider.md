# 0021 Claude as a direct provider through the official Anthropic SDK

- Date: 2026-11-25
- Status: accepted
- Decided by: Claude Code (Opus 5.5) as a subagent, on Paul's request to let Wings use Claude with a developer's own Anthropic key

## Context

A real Opus run on 2026-11-25 went through Anthropic's OpenAI-compatible endpoint with a throwaway script, because Wings had no Anthropic provider. It found three problems:

1. The endpoint answers `response_format: json_object` with 400. Wings sent it whenever no tools were offered.
2. There was no Anthropic provider and no way to point Wings at another endpoint.
3. Only OpenRouter reports a cost, so with any other provider the Activity view showed none.

Measured on that run: 16 calls, 170,432 input and 75,619 output tokens, 608.6 s; P4 Code alone 318 s.

## Decision

- **A fourth provider, `anthropic`**, implemented in `adapters/llm_anthropic.py` with the official `anthropic` Python SDK and the Messages API, not the OpenAI-compatible endpoint. Key `ANTHROPIC_API_KEY`; optional `ANTHROPIC_BASE_URL`. Defaults: small `claude-haiku-5-5`, mid and frontier `claude-sonnet-5-5`, editable in Settings.
- **Every answer is streamed** (`messages.stream` and `get_final_message`), so a 5-minute answer cannot time out.
- **No JSON mode on the Messages API.** The schema in the prompt, validation and the retry in `call_structured` already enforce JSON for every provider.
- **JSON mode is a capability of the OpenAI-compatible endpoint** (`OpenAICompatibleLLM(json_mode=...)`). OpenAI and OpenRouter keep it; an adapter for an endpoint that rejects it turns it off.
- **Two small port additions.** `LLMReply.provider_content` and `ChatTurn.provider_content` carry the provider's own content blocks of an assistant reply through `call_structured`, so Claude's thinking blocks go back unchanged with their tool calls. `LLMRequest.tool_choice` (`auto` or `none`) replaces removing the tools after the last tool round: Claude checks that the tool list under its thinking blocks did not change. The OpenAI-compatible adapters map `none` to their old behaviour (no tools, JSON mode).
- **Thinking stays at the model's default** (adaptive on current Claude models); the developer may set an effort per tier (`WINGS_EFFORT_<TIER>`, Settings). No `thinking` parameter is sent, so an older model id cannot make the request invalid.
- **Refusal fallback on by default** where the model supports it (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`): a declined request is rerun on a fallback model inside the same call instead of failing a step. A final refusal becomes `LLMError` with the category.
- **Cost from a price table** (`adapters/pricing.py`) when the provider reports none. A model without a price gives `cost_usd = None`, and an answer with any unknown call is None in total. The Activity view says "cost unknown" instead of "$0".

## Alternatives

- Keep using the OpenAI-compatible endpoint with JSON mode off: fewer lines, but no streaming helper, no effort, no refusal fallback, and thinking blocks would be lost in tool rounds.
- Raw HTTP with `httpx` like the OpenAI adapter: the SDK already handles streaming, retries and typed errors, and the `claude-api` skill Claude Code follows asks for the official SDK.
- Strip thinking blocks and remove the tools in the last round, as before: works on accounts the history check does not enforce, but fails with 400 on newer accounts.
- Prompt caching (`cache_control`): would make the tool rounds of one answer cheaper, but costs 1.25 x on every single-call answer. Left out until a real run shows the split.
- Eager input streaming for tools: lower latency for large tool inputs, but the API then stops validating the input. Wings' tool inputs are a few kilobytes; left off.

## Consequences

- New dependency `anthropic` (2.x). It brings its own HTTP client, `httpx2`; tests fake it with `httpx2.MockTransport` and server-sent events.
- API version 12: settings carry `efforts`, and `keys` and `defaults` list `anthropic`.
- Prices age. The table is dated; a new model id has an unknown cost until someone adds it.
- With a refusal fallback, `usage` may cover two models while the cost is priced at the model that finished; the cost is an estimate.
- No real call was made while building this (no paid calls by AI agents). The first real run is Paul's, and it should check: the tool round trip with thinking blocks, the last round with `tool_choice: none`, and the cost against the Claude Console.
