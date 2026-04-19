from __future__ import annotations
from interfaces.llm import LLMProvider
from bootstrap import state


def get_provider() -> LLMProvider:
    config = state.get_config()
    provider_name = config.get("llm", {}).get("provider", "openrouter")
    return _build(provider_name, config)


def _build(name: str, config: dict) -> LLMProvider:
    provider_config = config.get("llm", {}).get("providers", {}).get(name, {})

    if name == "openrouter":
        from services.llm.providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(
            base_url=provider_config.get("base_url", "https://openrouter.ai/api/v1"),
        )
    if name == "openai":
        from services.llm.providers.openai import OpenAIProvider
        return OpenAIProvider()
    if name == "anthropic":
        from services.llm.providers.anthropic import AnthropicProvider
        return AnthropicProvider()
    if name == "google":
        from services.llm.providers.google import GoogleProvider
        return GoogleProvider()

    raise ValueError(f"Unknown LLM provider: {name}")
