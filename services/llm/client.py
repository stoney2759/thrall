from __future__ import annotations
import logging
from typing import AsyncIterator
from bootstrap import state
from services.llm.router import get_provider
from schemas.llm import LLMResponse

logger = logging.getLogger(__name__)


def _llm_config() -> dict:
    return state.get_config().get("llm", {})


def _model(override: str | None) -> str:
    if override:
        return override
    if m := state.get_model_override():
        return m
    active_profile = state.get_active_llm_profile()
    if active_profile:
        from services.llm.router import get_model_for_profile
        profile_model = get_model_for_profile(active_profile)
        if profile_model:
            return profile_model
    return _llm_config().get("model", "anthropic/claude-sonnet-4-5")


async def complete(messages: list[dict], model: str | None = None) -> str:
    cfg = _llm_config()
    return await get_provider().complete(
        messages=messages,
        model=_model(model),
        temperature=cfg.get("temperature", 0.7),
        max_tokens=cfg.get("max_tokens", 8192),
    )


async def complete_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
) -> LLMResponse:
    cfg = _llm_config()
    provider = get_provider()
    resolved_model = _model(model)
    logger.info("LLM call: provider=%s model=%s", provider.name(), resolved_model)
    response = await provider.complete_with_tools(
        messages=messages,
        tools=tools,
        model=resolved_model,
        temperature=cfg.get("temperature", 0.7),
        max_tokens=cfg.get("max_tokens", 8192),
    )
    if not response.model:
        response.model = resolved_model
    return response


async def stream(messages: list[dict], model: str | None = None) -> AsyncIterator[str]:
    cfg = _llm_config()
    async for chunk in await get_provider().stream(
        messages=messages,
        model=_model(model),
        temperature=cfg.get("temperature", 0.7),
        max_tokens=cfg.get("max_tokens", 8192),
    ):
        yield chunk
