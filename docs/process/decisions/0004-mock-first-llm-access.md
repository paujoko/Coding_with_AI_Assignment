# 0004 Mock-first LLM access through one port, OpenRouter for real runs

- Date: 2026-11-09
- Status: accepted
- Decided by: Claude Code (Opus 5.5), following Paul's standing rule that only he triggers paid model calls

## Decision

- One `LLMClient` port. Default provider: a scripted mock that replays canned replies per agent. Real provider: OpenRouter (OpenAI-compatible), one key for small, mid and frontier models.
- Each agent declares a model tier; tiers map to model IDs through configuration.
- Structured output goes through one helper with schema-in-prompt, validation and one retry.

## Why

- The PDF warns that the demo must not depend on a single fragile API key and to mind rate limits and costs.
- The hands-on lecture used OpenRouter with small, mid and frontier models; the tier idea makes "which model for which agent" an explicit, reportable choice.
- AI coding agents must not spend money; a mock default makes that the path of least resistance.

## Consequences

- Demos can run fully offline on the mock (useful as the fallback for the live demo).
- The mock's replies do not depend on the input; real quality must be checked with real runs by a human.
- Model IDs in `config.py` are unverified guesses from the lecture slide and must be checked on openrouter.ai.
