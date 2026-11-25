"""Cost from tokens for providers that do not report it (Anthropic). Unknown stays unknown, never 0."""

import pytest

from wings.adapters.pricing import cost_usd


def test_input_and_output_are_priced_per_million_tokens():
    assert cost_usd("claude-opus-5-5", input_tokens=1_000_000, output_tokens=1_000_000) == pytest.approx(4.0 + 20.0)
    assert cost_usd("claude-sonnet-5-5", input_tokens=500_000, output_tokens=0) == pytest.approx(1.0)


def test_cache_reads_and_writes_have_their_own_rates():
    # Sonnet 5.5: cache reads $0.10 per million, 5-minute cache writes 1.25 x input ($2.50)
    assert cost_usd("claude-sonnet-5-5", 0, 0, cache_read_tokens=1_000_000, cache_write_tokens=1_000_000) == pytest.approx(0.10 + 2.50)


def test_haiku_costs_more_above_100k_prompt_tokens():
    assert cost_usd("claude-haiku-5-5", 100_000, 0) == pytest.approx(0.01)
    assert cost_usd("claude-haiku-5-5", 200_000, 1_000_000) == pytest.approx(0.10 + 2.50)


def test_unknown_models_and_unknown_cache_prices_give_none():
    assert cost_usd("gpt-5", 1000, 1000) is None  # no OpenAI prices in the table
    assert cost_usd("claude-haiku-5-5", 10, 10, cache_read_tokens=5) is None  # its cache read price is not in the table
