from __future__ import annotations
import asyncio
import json
import os
import re
import uuid
from typing import AsyncIterator
import httpx
from interfaces.llm import LLMProvider
from schemas.llm import LLMResponse, ToolCallRequest
from bootstrap import state

_XML_TOOL_RE = re.compile(
    r"<tool_call>\s*<function=([^>]+)>(.*?)</function>\s*</tool_call>",
    re.DOTALL,
)
_PARAM_RE = re.compile(r"<parameter=([^>]+)>(.*?)</parameter>", re.DOTALL)

_MAX_RETRIES = 3
_RETRY_BASE = 5  # seconds — doubles each attempt: 5, 10, 20


def _parse_xml_tool_calls(content: str) -> tuple[list[ToolCallRequest], str]:
    calls: list[ToolCallRequest] = []
    remaining = content

    for match in _XML_TOOL_RE.finditer(content):
        name = match.group(1).strip()
        body = match.group(2)
        args: dict = {}

        body_stripped = body.strip()
        if body_stripped.startswith("{"):
            try:
                args = json.loads(body_stripped)
            except json.JSONDecodeError:
                pass
        if not args:
            for p in _PARAM_RE.finditer(body):
                args[p.group(1).strip()] = p.group(2).strip()

        calls.append(ToolCallRequest(
            id=f"xml-{uuid.uuid4().hex[:8]}",
            name=name,
            args=args,
        ))
        remaining = remaining.replace(match.group(0), "").strip()

    return calls, remaining


async def _post_with_retry(client: httpx.AsyncClient, url: str, headers: dict, payload: dict) -> httpx.Response:
    for attempt in range(_MAX_RETRIES):
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 429:
            wait = _RETRY_BASE * (2 ** attempt)
            await asyncio.sleep(wait)
            continue
        response.raise_for_status()
        return response
    # Final attempt — let it raise naturally
    response = await client.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, base_url: str = "https://openrouter.ai/api/v1") -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._base_url = base_url

    def name(self) -> str:
        return "openrouter"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thrall.ai",
        }

    def _reasoning_payload(self) -> dict:
        effort = state.get_reasoning_effort() or state.get_config().get("llm", {}).get("reasoning_effort")
        if effort:
            return {"reasoning": {"effort": effort}}
        return {}

    async def complete(self, messages: list[dict], model: str, temperature: float, max_tokens: int) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
            payload.update(self._reasoning_payload())
            response = await _post_with_retry(client, f"{self._base_url}/chat/completions", self._headers(), payload)
            return response.json()["choices"][0]["message"]["content"]

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], model: str, temperature: float, max_tokens: int,
    ) -> LLMResponse:
        async with httpx.AsyncClient(timeout=90.0) as client:
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            payload.update(self._reasoning_payload())
            response = await _post_with_retry(client, f"{self._base_url}/chat/completions", self._headers(), payload)
            data = response.json()
            message = data["choices"][0]["message"]
            finish_reason = data["choices"][0].get("finish_reason", "stop")

            tool_calls: list[ToolCallRequest] = []
            for tc in message.get("tool_calls") or []:
                tool_calls.append(ToolCallRequest(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    args=json.loads(tc["function"]["arguments"]),
                ))

            content = message.get("content") or ""

            if not tool_calls and content:
                tool_calls, content = _parse_xml_tool_calls(content)

            return LLMResponse(
                content=content or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )

    async def stream(self, messages: list[dict], model: str, temperature: float, max_tokens: int) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if content := delta.get("content"):
                            yield content
