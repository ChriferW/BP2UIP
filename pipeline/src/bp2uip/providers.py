"""Pluggable LLM provider interface.

All LLM access in the codebase goes through LLMProvider; no other
module may call a provider SDK. API keys come from environment
variables only and never appear in code, config files, or artifacts.
Artifacts record provider and model names, never credentials.
"""

import os
from dataclasses import dataclass
from typing import Protocol

# Default model for the Anthropic provider; override per run with
# `bp2uip extract --model`. The exact model string used is recorded in
# each spec's extraction metadata.
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"

ENV_PROVIDER = "BP2UIP_PROVIDER"
ENV_ANTHROPIC_KEY = "ANTHROPIC_API_KEY"
ENV_OPENAI_KEY = "OPENAI_API_KEY"


class ProviderConfigError(Exception):
    """A provider is unknown or its API key environment variable is unset."""


@dataclass
class CompletionResult:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    name: str

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096
    ) -> CompletionResult: ...


class AnthropicProvider:
    """Primary provider. Implemented in roadmap week 3."""

    name = "anthropic"

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL) -> None:
        if not os.environ.get(ENV_ANTHROPIC_KEY):
            raise ProviderConfigError(f"{ENV_ANTHROPIC_KEY} is not set")
        self.model = model

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096
    ) -> CompletionResult:
        raise NotImplementedError("Anthropic provider is implemented in roadmap week 3")


class OpenAIProvider:
    """Stub with the same shape as AnthropicProvider; proves the interface is pluggable."""

    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        if not os.environ.get(ENV_OPENAI_KEY):
            raise ProviderConfigError(f"{ENV_OPENAI_KEY} is not set")
        self.model = model

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096
    ) -> CompletionResult:
        raise NotImplementedError("OpenAI provider is a stub; Anthropic is the primary provider")


class FakeProvider:
    """Test double: returns canned responses in order. Never used outside tests."""

    name = "fake"

    def __init__(self, responses: list[str], model: str = "fake-model") -> None:
        self._responses = list(responses)
        self.model = model

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096
    ) -> CompletionResult:
        if not self._responses:
            raise AssertionError("FakeProvider ran out of canned responses")
        return CompletionResult(text=self._responses.pop(0), model=self.model)


def get_provider(name: str | None = None) -> LLMProvider:
    """Select a provider by name, or by BP2UIP_PROVIDER, defaulting to anthropic.

    An explicit name (the CLI --provider flag) wins over the
    environment variable.
    """
    resolved = name or os.environ.get(ENV_PROVIDER) or "anthropic"
    if resolved == "anthropic":
        return AnthropicProvider()
    if resolved == "openai":
        return OpenAIProvider()
    raise ProviderConfigError(f"unknown provider: {resolved}")
