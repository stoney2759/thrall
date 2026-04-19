from __future__ import annotations
from typing import AsyncIterator
from bootstrap import state
from services.llm.router import get_provider
from schemas.llm import LLMResponse


def _llm_config() -> dict:
    return state.get_config().get("llm", {})


def _model(override: str | None) -> str:
    return override or state.get_model_override() or _llm_config().get("model", "anthropic/claude-sonnet-4-5")


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
    return await get_provider().complete_with_tools(
        messages=messages,
        tools=tools,
        model=_model(model),
        temperature=cfg.get("temperature", 0.7),
        max_tokens=cfg.get("max_tokens", 8192),
    )


async def stream(messages: list[dict], model: str | None = None) -> AsyncIterator[str]:
    cfg = _llm_config()
    async for chunk in await get_provider().stream(
        messages=messages,
        model=_model(model),
        temperature=cfg.get("temperature", 0.7),
        max_tokens=cfg.get("max_tokens", 8192),
    ):
        yield chunk
