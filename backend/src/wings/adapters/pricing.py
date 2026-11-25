"""Cost of one model call from its tokens, for providers that do not report a cost themselves.

OpenRouter reports the cost of each call; Anthropic and OpenAI do not. For those the adapter asks
here. A model that is not in the table has an unknown cost (None), never 0: the Activity view then
says "cost unknown". Prices are USD per million tokens, Anthropic's first-party API rates as listed
in Anthropic's model docs on 2026-11-03. Check them when a model is added; OpenAI is left out on
purpose because we could not confirm its current rates.
"""

from dataclasses import dataclass

CACHE_WRITE_FACTOR = 1.25  # 5-minute cache writes cost 1.25 x the input rate


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float | None = None  # None: not known; a call that reads the cache then has an unknown cost
    long_above: int | None = None  # prompt tokens above which the long-context rates apply
    long_input: float | None = None
    long_output: float | None = None


PRICES: dict[str, Price] = {
    "claude-opus-5-5": Price(4.00, 20.00, cache_read=0.20),
    "claude-sonnet-5-5": Price(2.00, 10.00, cache_read=0.10),
    "claude-haiku-5-5": Price(0.10, 0.50, long_above=100_000, long_input=0.50, long_output=2.50),
    "claude-fable-5-2": Price(8.00, 40.00, cache_read=0.20),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float | None:
    """USD for one call. `input_tokens` are the uncached input tokens (Anthropic's `input_tokens`)."""
    price = PRICES.get(model.strip().lower())
    if price is None:
        return None
    rate_in, rate_out = price.input, price.output
    prompt = input_tokens + cache_read_tokens + cache_write_tokens
    if price.long_above is not None and prompt > price.long_above:
        rate_in, rate_out = price.long_input or rate_in, price.long_output or rate_out
    if cache_read_tokens and price.cache_read is None:
        return None
    total = input_tokens * rate_in + output_tokens * rate_out
    total += cache_write_tokens * rate_in * CACHE_WRITE_FACTOR
    total += cache_read_tokens * (price.cache_read or 0.0)
    return total / 1_000_000
