from __future__ import annotations
import os
from typing import AsyncIterator
import httpx
from interfaces.llm import LLMProvider
from services.llm._retry import post_with_retry


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._base_url = "https://api.anthropic.com/v1"

    def name(self) -> str:
        return "anthropic"

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _to_anthropic_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        system = None
        converted = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                converted.append({"role": msg["role"], "content": msg["content"]})
        return system, converted

    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        system, msgs = self._to_anthropic_messages(messages)
        body = {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await post_with_retry(
                client, f"{self._base_url}/messages",
                headers=self._headers(), json=body, provider="anthropic",
            )
            return response.json()["content"][0]["text"]

    async def stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        system, msgs = self._to_anthropic_messages(messages)
        body = {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/messages",
                headers=self._headers(),
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        event = json.loads(line[6:])
                        if event.get("type") == "content_block_delta":
                            if text := event.get("delta", {}).get("text"):
                                yield text
