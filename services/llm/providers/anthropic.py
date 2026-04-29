from __future__ import annotations
import json
import os
from typing import AsyncIterator
import httpx
from interfaces.llm import LLMProvider
from schemas.llm import LLMResponse, ToolCallRequest
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

    def _to_anthropic_tools(self, tools: list[dict]) -> list[dict]:
        result = []
        for tool in tools:
            fn = tool.get("function", {})
            result.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return result

    def _to_anthropic_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        system = None
        converted = []
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system = (system + "\n\n" + msg["content"]) if system else msg["content"]
                continue
            if role == "assistant":
                tool_calls = msg.get("tool_calls", [])
                content = msg.get("content")
                if tool_calls:
                    blocks = []
                    if content:
                        blocks.append({"type": "text", "text": content})
                    for tc in tool_calls:
                        args = tc["function"]["arguments"]
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"], "input": args})
                    converted.append({"role": "assistant", "content": blocks})
                else:
                    converted.append({"role": "assistant", "content": content or ""})
                continue
            if role == "tool":
                block = {"type": "tool_result", "tool_use_id": msg.get("tool_call_id", ""), "content": msg.get("content", "")}
                if converted and converted[-1]["role"] == "user" and isinstance(converted[-1]["content"], list):
                    converted[-1]["content"].append(block)
                else:
                    converted.append({"role": "user", "content": [block]})
                continue
            converted.append({"role": role, "content": msg.get("content", "")})
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

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], model: str, temperature: float, max_tokens: int,
    ) -> LLMResponse:
        system, msgs = self._to_anthropic_messages(messages)
        body: dict = {
            "model": model,
            "messages": msgs,
            "tools": self._to_anthropic_tools(tools),
            "tool_choice": {"type": "auto"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                raw = await post_with_retry(
                    client, f"{self._base_url}/messages",
                    headers=self._headers(), json=body, provider="anthropic",
                )
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Anthropic {e.response.status_code}: {e.response.text[:500]}") from e
            data = raw.json()

        text_content = ""
        tool_calls: list[ToolCallRequest] = []
        for block in data.get("content", []):
            if block["type"] == "text":
                text_content += block.get("text", "")
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block["id"],
                    name=block["name"],
                    args=block.get("input", {}),
                ))

        return LLMResponse(
            content=text_content or None,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
        )

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
