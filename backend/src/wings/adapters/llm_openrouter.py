"""OpenRouter adapter: one key gives access to small, mid and frontier models of many vendors.

Same wire format as OpenAI (see llm_openai.py), plus OpenRouter's cost reporting.
"""

import httpx

from wings.adapters.llm_openai import OpenAICompatibleLLM
from wings.application.ports import Tier

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLM(OpenAICompatibleLLM):
    provider = "OpenRouter"
    key_name = "OPENROUTER_API_KEY"

    def __init__(
        self,
        api_key: str,
        models: dict[Tier, str],
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 180.0,
    ):
        super().__init__(
            api_key,
            models,
            base_url,
            client=client,
            timeout=timeout,
            extra_body={"usage": {"include": True}},  # makes OpenRouter report the cost of each call
            extra_headers={"X-Title": "Wings (HSG Coding with AI)"},
        )
