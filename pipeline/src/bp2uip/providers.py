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
    """Primary provider."""

    name = "anthropic"

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL) -> None:
        if not os.environ.get(ENV_ANTHROPIC_KEY):
            raise ProviderConfigError(f"{ENV_ANTHROPIC_KEY} is not set")
        self.model = model

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096
    ) -> CompletionResult:
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderConfigError(
                "the 'anthropic' package is not installed; install the pipeline dependencies first"
            ) from exc
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            kwargs["system"] = system
        message = client.messages.create(**kwargs)
        text = "".join(block.text for block in message.content if block.type == "text")
        # message.model is the exact string the API served, recorded verbatim
        # in the spec's extraction metadata.
        return CompletionResult(
            text=text,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )


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
        self.prompts: list[str] = []  # every prompt received, for test assertions

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096
    ) -> CompletionResult:
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("FakeProvider ran out of canned responses")
        return CompletionResult(text=self._responses.pop(0), model=self.model)


def get_provider(name: str | None = None, model: str | None = None) -> LLMProvider:
    """Select a provider by name, or by BP2UIP_PROVIDER, defaulting to anthropic.

    An explicit name (the CLI --provider flag) wins over the
    environment variable. model overrides the provider's default.
    """
    resolved = name or os.environ.get(ENV_PROVIDER) or "anthropic"
    if resolved == "anthropic":
        return AnthropicProvider(model=model) if model else AnthropicProvider()
    if resolved == "openai":
        return OpenAIProvider(model=model)
    raise ProviderConfigError(f"unknown provider: {resolved}")
