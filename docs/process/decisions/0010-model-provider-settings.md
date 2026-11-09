# 0010 Model provider chosen in the UI, stored in .env, swapped at runtime

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5) on Paul's request ("dass ich nur noch meinen Open AI token rein pasten muss und es geht")

## Decision

- OpenAI is a provider next to the mock and OpenRouter; both real adapters share one OpenAI-compatible base class.
- `.env` at the repository root is read at start (real environment variables win) and written by the Settings page through `PUT /api/settings/llm`. It is git-ignored.
- The composition root (`bootstrap.LLMSettings`) rebuilds the LLM client and swaps `orchestrator.llm` at once; the API only knows the `LLMSettingsService` port, so the layer rules hold.
- Keys never leave the backend again: views carry only `sk-…1234`.
- A real provider without a key is replaced by `NotConfiguredLLM`, which explains how to add the key; the app keeps running.

## Alternatives

- Keys only in environment variables: hard on Windows and the reason Paul asked.
- Keys in the browser (localStorage) sent with each request: the key would travel with every request and live in the browser profile.

## Consequences

- Anyone who can reach the backend can change the provider; it binds to localhost by default. Do not expose it on a network without authentication.
- Default model names will age; they are editable in Settings and in `.env`.
