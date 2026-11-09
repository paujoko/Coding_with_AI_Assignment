"""OpenRouter adapter (OpenAI-compatible chat completions).

One key gives access to small, mid and frontier models; the tier of the
calling agent picks the model. Only humans run this against the real API;
tests use httpx.MockTransport.
"""

import httpx

from wings.application.ports import LLMError, LLMReply, LLMRequest, Tier

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLM:
    def __init__(
        self,
        api_key: str,
        models: dict[Tier, str],
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 180.0,
    ):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is empty.")
        self._models = models
        self._client = client or httpx.Client(timeout=timeout)
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", "X-Title": "Wings (HSG Coding with AI)"}

    def complete(self, request: LLMRequest) -> LLMReply:
        model = self._models[request.tier]
        body: dict = {
            "model": model,
            "messages": [{"role": "system", "content": request.system}]
            + [{"role": t.role, "content": t.content} for t in request.messages],
            "usage": {"include": True},
        }
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.post(self._url, json=body, headers=self._headers)
        except httpx.HTTPError as err:
            raise LLMError(f"OpenRouter request failed: {err}") from err
        if resp.status_code >= 400:
            raise LLMError(f"OpenRouter returned {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as err:
            raise LLMError(f"Unexpected OpenRouter response: {str(data)[:300]}") from err
        usage = data.get("usage") or {}
        return LLMReply(
            text=text,
            model=data.get("model", model),
            usage={k: v for k, v in usage.items() if isinstance(v, int)},
            cost_usd=usage.get("cost"),
        )
