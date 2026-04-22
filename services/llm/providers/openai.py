from __future__ import annotations
import os
from typing import AsyncIterator
import httpx
from interfaces.llm import LLMProvider
from services.llm._retry import post_with_retry


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = "https://api.openai.com/v1"

    def name(self) -> str:
        return "openai"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await post_with_retry(
                client, f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                provider="openai",
            )
            return response.json()["choices"][0]["message"]["content"]

    async def stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if content := delta.get("content"):
                            yield content
