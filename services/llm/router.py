from __future__ import annotations
import logging
from pathlib import Path
from interfaces.llm import LLMProvider
from bootstrap import state

logger = logging.getLogger(__name__)

_PROFILES_FILE = Path(__file__).parent.parent.parent / "config" / "profiles.toml"


def get_provider() -> LLMProvider:
    """Return the active LLM provider. Checks active LLM profile first, falls back to config."""
    active_profile = state.get_active_llm_profile()
    if active_profile:
        profile = _load_profile(active_profile)
        if profile:
            return _build(profile["provider"], state.get_config())

    config = state.get_config()
    provider_name = config.get("llm", {}).get("provider", "openrouter")
    return _build(provider_name, config)


def get_model_for_profile(profile_name: str) -> str | None:
    """Return the model string for a named profile, or None if not found."""
    profile = _load_profile(profile_name)
    return profile.get("model") if profile else None


def list_profiles() -> dict[str, dict]:
    """Return all defined profiles from profiles.toml."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            logger.error("No TOML parser available — install tomli or use Python 3.11+")
            return {}
    if not _PROFILES_FILE.exists():
        return {}
    try:
        data = tomllib.loads(_PROFILES_FILE.read_text(encoding="utf-8"))
        return data.get("profiles", {})
    except Exception as e:
        logger.error("Failed to load profiles.toml: %s", e)
        return {}


def _load_profile(name: str) -> dict | None:
    profiles = list_profiles()
    return profiles.get(name)


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
    if name == "anthropic_cli":
        from services.llm.providers.anthropic_cli import AnthropicCliProvider
        return AnthropicCliProvider()
    if name == "openai_codex":
        from services.auth import credentials
        from services.llm.providers.openai_codex import OpenAICodexProvider
        cred = credentials.get("openai") or {}
        token = credentials.get_token("openai") or ""
        account_id = cred.get("account_id", "")
        return OpenAICodexProvider(api_key=token, account_id=account_id)
    if name == "google":
        from services.llm.providers.google import GoogleProvider
        return GoogleProvider()

    raise ValueError(f"Unknown LLM provider: {name}")
