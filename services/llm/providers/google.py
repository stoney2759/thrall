from __future__ import annotations
import os
from typing import AsyncIterator
import httpx
from interfaces.llm import LLMProvider


class GoogleProvider(LLMProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"

    def name(self) -> str:
        return "google"

    def _to_google_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        system = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        return system, contents

    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        system, contents = self._to_google_messages(messages)
        body: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/models/{model}:generateContent",
                params={"key": self._api_key},
                json=body,
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        system, contents = self._to_google_messages(messages)
        body: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/models/{model}:streamGenerateContent",
                params={"key": self._api_key, "alt": "sse"},
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        event = json.loads(line[6:])
                        try:
                            yield event["candidates"][0]["content"]["parts"][0]["text"]
                        except (KeyError, IndexError):
                            continue
