"""OpenAI-compatible chat completions: OpenAI itself, and OpenRouter (see llm_openrouter.py).

The tier of the calling agent picks the model. Only humans run this against a real API;
tests use httpx.MockTransport.
"""

import httpx

from wings.application.ports import LLMError, LLMReply, LLMRequest, Tier

OPENAI_BASE_URL = "https://api.openai.com/v1"

# What to tell the developer for the errors people actually hit.
_HINTS = {
    401: "the API key is wrong or revoked; paste a new one in Settings",
    403: "the key has no access to this model or project",
    404: "the model name does not exist for this key; check the models in Settings",
    429: "rate limit or no credit left on the account",
}


class OpenAICompatibleLLM:
    provider = "OpenAI-compatible API"
    key_name = "API key"

    def __init__(
        self,
        api_key: str,
        models: dict[Tier, str],
        base_url: str,
        client: httpx.Client | None = None,
        timeout: float = 180.0,
        extra_body: dict | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        if not api_key:
            raise ValueError(f"{self.key_name} is empty.")
        self._models = models
        self._client = client or httpx.Client(timeout=timeout)
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", **(extra_headers or {})}
        self._extra = extra_body or {}

    def complete(self, request: LLMRequest) -> LLMReply:
        model = self._models[request.tier]
        body: dict = {
            "model": model,
            "messages": [{"role": "system", "content": request.system}]
            + [{"role": t.role, "content": t.content} for t in request.messages],
            **self._extra,
        }
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.post(self._url, json=body, headers=self._headers)
        except httpx.HTTPError as err:
            raise LLMError(f"{self.provider} request failed: {err}") from err
        if resp.status_code >= 400:
            hint = _HINTS.get(resp.status_code)
            raise LLMError(f"{self.provider} returned {resp.status_code}{f' ({hint})' if hint else ''}: {resp.text[:300]}")
        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as err:  # ValueError covers non-JSON bodies
            raise LLMError(f"Unexpected {self.provider} response: {resp.text[:300]}") from err
        usage = data.get("usage") or {}
        return LLMReply(
            text=text,
            model=data.get("model", model),
            usage={k: v for k, v in usage.items() if isinstance(v, int)},
            cost_usd=usage.get("cost"),
        )


class OpenAILLM(OpenAICompatibleLLM):
    provider = "OpenAI"
    key_name = "OPENAI_API_KEY"

    def __init__(self, api_key: str, models: dict[Tier, str], client: httpx.Client | None = None, timeout: float = 180.0):
        super().__init__(api_key, models, OPENAI_BASE_URL, client=client, timeout=timeout)
