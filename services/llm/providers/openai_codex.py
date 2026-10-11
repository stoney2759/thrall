"""OpenAI Codex provider — chatgpt.com/backend-api/codex/responses.

Uses the ChatGPT backend (included with Pro/Plus subscription) authenticated
via OAuth PKCE token. This is NOT the OpenAI API — no API billing required.

Key differences from Chat Completions API:
- stream: true is required (the endpoint rejects stream: false)
- Tools use flat format: {type, name, description, parameters} not nested function wrapper
- Tool results use type: function_call_output, not role: tool
- Assistant tool calls in history are individual function_call items, not tool_calls array
- System messages go into a single top-level `instructions` string
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from interfaces.llm import LLMProvider
from schemas.llm import LLMResponse, LLMUsage, ToolCallRequest

logger = logging.getLogger(__name__)

_BASE_URL = "https://chatgpt.com/backend-api/codex"


class OpenAICodexProvider(LLMProvider):
    """Calls the ChatGPT Codex backend using a Pro/Plus subscription OAuth token."""

    def __init__(self, api_key: str, account_id: str = "") -> None:
        self._api_key = api_key
        self._account_id = account_id

    def name(self) -> str:
        return "openai_codex"

    def _headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._account_id:
            h["ChatGPT-Account-ID"] = self._account_id
        return h

    # ── format conversion ─────────────────────────────────────────────────────

    @staticmethod
    def _to_responses_input(messages: list[dict]) -> tuple[str, list[dict]]:
        """Convert Chat Completions messages → Codex Responses API format.

        - system messages → joined into single instructions string
        - role: tool → type: function_call_output
        - assistant tool_calls → individual type: function_call items
        """
        instructions_parts: list[str] = []
        input_items: list[dict] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                block = content if isinstance(content, str) else json.dumps(content)
                if block:
                    instructions_parts.append(block)

            elif role == "tool":
                input_items.append({
                    "type": "function_call_output",
                    "call_id": msg.get("tool_call_id", ""),
                    "output": content if isinstance(content, str) else json.dumps(content),
                })

            elif role == "assistant":
                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    input_items.append({
                        "type": "function_call",
                        "call_id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "arguments": fn.get("arguments", "{}"),
                    })
                if content:
                    input_items.append({
                        "role": "assistant",
                        "content": content if isinstance(content, str) else json.dumps(content),
                    })

            else:
                input_items.append({
                    "role": role,
                    "content": content if isinstance(content, str) else json.dumps(content),
                })

        return "\n\n".join(instructions_parts), input_items

    @staticmethod
    def _to_responses_tools(tools: list[dict]) -> list[dict]:
        """Convert Chat Completions nested tool format → Codex flat format."""
        out = []
        for t in tools:
            if t.get("type") == "function" and "function" in t:
                fn = t["function"]
                out.append({
                    "type": "function",
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                })
            else:
                out.append(t)
        return out

    # ── token refresh ─────────────────────────────────────────────────────────

    async def _try_refresh(self) -> bool:
        """Refresh the OAuth token using the stored refresh_token."""
        try:
            from services.auth import credentials
            from services.auth.oauth_openai import refresh_token as _refresh
            cred = credentials.get("openai") or {}
            refresh_tok = cred.get("refresh_token", "")
            if not refresh_tok:
                logger.warning("openai_codex: no refresh token stored — run /auth @openai")
                return False
            new_creds = await _refresh(refresh_tok)
            credentials.write_oauth(
                profile_name="openai",
                access_token=new_creds["access_token"],
                refresh_token=new_creds.get("refresh_token", refresh_tok),
                expires_at=new_creds.get("expires_at", 0),
                account_id=new_creds.get("account_id", self._account_id),
            )
            self._api_key = new_creds["access_token"]
            if new_creds.get("account_id"):
                self._account_id = new_creds["account_id"]
            logger.info("openai_codex: token refreshed successfully")
            return True
        except Exception as exc:
            logger.error("openai_codex: token refresh failed: %s", exc)
            return False

    # ── streaming consumer ────────────────────────────────────────────────────

    async def _stream_collect(
        self,
        payload: dict,
        _retried: bool = False,
    ) -> LLMResponse:
        """Stream the Codex endpoint and collect into a complete LLMResponse."""
        text_parts: list[str] = []
        func_calls: dict[int, dict] = {}
        usage_raw: dict = {}

        timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{_BASE_URL}/responses",
                headers={**self._headers(), "Accept": "text/event-stream"},
                json=payload,
            ) as response:
                if response.status_code == 401 and not _retried:
                    logger.warning("openai_codex: 401 — attempting token refresh")
                    if await self._try_refresh():
                        return await self._stream_collect(payload, _retried=True)
                if not response.is_success:
                    body = await response.aread()
                    logger.error("openai_codex %d: %s", response.status_code, body[:500])
                    try:
                        detail = json.loads(body).get("detail") or json.loads(body).get("error", {}).get("message", "")
                        raise RuntimeError(f"ChatGPT Codex {response.status_code}: {detail}")
                    except (json.JSONDecodeError, AttributeError):
                        response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    ev_type = ev.get("type", "")
                    logger.debug("codex SSE event: type=%s keys=%s", ev_type, list(ev.keys()))

                    if ev_type == "response.output_text.delta":
                        delta = ev.get("delta", "")
                        if delta:
                            text_parts.append(delta)

                    elif ev_type == "response.output_item.added":
                        item = ev.get("item", {})
                        if item.get("type") == "function_call":
                            idx = ev.get("output_index", 0)
                            func_calls[idx] = {
                                "call_id": item.get("call_id", ""),
                                "name": item.get("name", ""),
                                "args_buf": item.get("arguments", ""),
                            }

                    elif ev_type == "response.output_item.done":
                        item = ev.get("item", {})
                        if item.get("type") == "function_call":
                            idx = ev.get("output_index", 0)
                            # Overwrite with complete data — done event has final call_id, name, arguments
                            func_calls[idx] = {
                                "call_id": item.get("call_id", ""),
                                "name": item.get("name", ""),
                                "args_buf": item.get("arguments", ""),
                            }

                    elif ev_type == "response.function_call_arguments.delta":
                        idx = ev.get("output_index", 0)
                        if idx in func_calls:
                            func_calls[idx]["args_buf"] += ev.get("delta", "")

                    elif ev_type == "response.function_call_arguments.done":
                        idx = ev.get("output_index", 0)
                        if idx in func_calls:
                            func_calls[idx]["args_buf"] = ev.get("arguments", func_calls[idx]["args_buf"])

                    elif ev_type == "response.completed":
                        usage_raw = ev.get("response", {}).get("usage", {})

        tool_calls: list[ToolCallRequest] = []
        for fc in func_calls.values():
            try:
                args = json.loads(fc["args_buf"]) if fc["args_buf"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCallRequest(
                id=fc["call_id"],
                name=fc["name"],
                args=args,
            ))

        usage = LLMUsage(
            prompt_tokens=usage_raw.get("input_tokens", 0),
            completion_tokens=usage_raw.get("output_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )
        content = "".join(text_parts) or None
        finish_reason = "tool_calls" if tool_calls else "stop"

        logger.debug(
            "openai_codex response: text=%d tool_calls=%d tokens=%d",
            len(content or ""), len(tool_calls), usage.total_tokens,
        )
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    # ── LLMProvider interface ─────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        result = await self.complete_with_tools(messages, [], model, temperature, max_tokens)
        return result.content or ""

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        instructions, input_items = self._to_responses_input(messages)
        payload: dict = {
            "model": model,
            "input": input_items,
            "stream": True,
            "store": False,
        }
        if instructions:
            payload["instructions"] = instructions
        if tools:
            payload["tools"] = self._to_responses_tools(tools)

        tool_names = [t.get("name", "?") for t in payload.get("tools", [])]
        logger.debug(
            "openai_codex request: model=%s input=%d tools=%d names=%s",
            model, len(input_items), len(tools), tool_names,
        )
        return await self._stream_collect(payload)

    async def stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        result = await self.complete_with_tools(messages, [], model, temperature, max_tokens)
        if result.content:
            yield result.content
        # Note: stream() is text-only — tool calls from the underlying call are dropped.
        # The coordinator always calls complete_with_tools() directly for tool-enabled turns.
