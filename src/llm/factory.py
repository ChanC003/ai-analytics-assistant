"""Factory: (provider_key, model, api_key) -> a ready LLMProvider.

This is the only place that knows how to construct each provider kind. The UI
passes the user's dropdown choices straight through here.
"""

from __future__ import annotations

from src.config import PROVIDER_REGISTRY, env_api_key, resolve_base_url
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.base import LLMError, LLMProvider
from src.llm.ollama_provider import OllamaProvider
from src.llm.openai_compatible import OpenAICompatibleProvider


def get_provider(
    provider_key: str,
    model: str = "",
    api_key: str = "",
) -> LLMProvider:
    spec = PROVIDER_REGISTRY.get(provider_key)
    if spec is None:
        raise LLMError(f"Unknown provider '{provider_key}'.")

    model = model or spec.models[0]
    base_url = resolve_base_url(spec)

    if spec.kind == "ollama":
        return OllamaProvider(model=model, base_url=base_url)

    # UI-typed key wins; otherwise fall back to the env default.
    key = api_key or env_api_key(provider_key)

    if spec.kind == "anthropic":
        return AnthropicProvider(model=model, api_key=key)

    if spec.kind == "openai_compatible":
        return OpenAICompatibleProvider(model=model, api_key=key, base_url=base_url)

    raise LLMError(f"Unsupported provider kind '{spec.kind}'.")
