"""Stands in for a real provider that has no API key yet: every call explains how to fix it."""

from wings.application.ports import LLMError, LLMReply, LLMRequest


class NotConfiguredLLM:
    def __init__(self, provider: str, key_name: str):
        self.provider = provider
        self.key_name = key_name

    def complete(self, request: LLMRequest) -> LLMReply:
        raise LLMError(f"No {self.provider} API key yet. Open Settings in Wings and paste it (or set {self.key_name} in .env).")
