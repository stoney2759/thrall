from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import uuid
from typing import AsyncIterator
import httpx
from interfaces.llm import LLMProvider
from schemas.llm import LLMResponse, LLMUsage, ToolCallRequest
from bootstrap import state
from constants.llm import MAX_RETRIES, RETRY_BASE_SECONDS

logger = logging.getLogger(__name__)

_XML_TOOL_RE = re.compile(
    r"<tool_call>\s*<function=([^>]+)>(.*?)</function>\s*</tool_call>",
    re.DOTALL,
)
_PARAM_RE = re.compile(r"<parameter=([^>]+)>(.*?)</parameter>", re.DOTALL)


# ── OpenRouter error taxonomy ──────────────────────────────────────────────────

class OpenRouterError(RuntimeError):
    def __init__(self, code: int | str, message: str, metadata: dict | None = None):
        self.code = code
        self.metadata = metadata or {}
        super().__init__(f"OpenRouter {code}: {message}")

class OpenRouterAuthError(OpenRouterError):
    """401 — Invalid or missing API key."""

class OpenRouterInsufficientCreditsError(OpenRouterError):
    """402 — Insufficient credits."""

class OpenRouterForbiddenError(OpenRouterError):
    """403 — Model restricted or requires moderation."""

class OpenRouterTimeoutError(OpenRouterError):
    """408 — Provider timed out."""

class OpenRouterRateLimitError(OpenRouterError):
    """429 — Rate limit hit."""

class OpenRouterModelUnavailableError(OpenRouterError):
    """502/503 — Model or provider is down."""

class OpenRouterBadRequestError(OpenRouterError):
    """400 — Bad request: invalid params, unknown model, etc."""


_CODE_MAP: dict[int, type[OpenRouterError]] = {
    400: OpenRouterBadRequestError,
    401: OpenRouterAuthError,
    402: OpenRouterInsufficientCreditsError,
    403: OpenRouterForbiddenError,
    408: OpenRouterTimeoutError,
    429: OpenRouterRateLimitError,
    502: OpenRouterModelUnavailableError,
    503: OpenRouterModelUnavailableError,
}


def _raise_openrouter_error(code: int | str, message: str, metadata: dict | None = None) -> None:
    cls = _CODE_MAP.get(int(code) if str(code).isdigit() else 0, OpenRouterError)
    err = cls(code, message, metadata)
    if metadata:
        logger.error("OpenRouter API error — %s | metadata: %s", err, metadata)
    else:
        logger.error("OpenRouter API error — %s", err)
    raise err


def _check_body(data: dict) -> None:
    if "error" not in data:
        return
    err = data["error"]
    _raise_openrouter_error(err.get("code", 0), err.get("message", str(err)), err.get("metadata"))


# ── HTTP layer ─────────────────────────────────────────────────────────────────

async def _post_with_retry(
    client: httpx.AsyncClient, url: str, headers: dict, payload: dict, model: str = "",
    max_retries: int = MAX_RETRIES, retry_base: int = RETRY_BASE_SECONDS,
) -> httpx.Response:
    for attempt in range(max_retries):
        response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 429:
            wait = retry_base * (2 ** attempt)
            logger.warning("OpenRouter rate limit (model=%s) — retrying in %ss (attempt %d/%d)", model, wait, attempt + 1, max_retries)
            await asyncio.sleep(wait)
            continue

        if response.status_code >= 400:
            try:
                body = response.json()
                logger.error("OpenRouter %s raw body: %s", response.status_code, json.dumps(body)[:1000])
                err = body.get("error", {})
                _raise_openrouter_error(
                    err.get("code", response.status_code),
                    err.get("message", response.text[:300]),
                    err.get("metadata"),
                )
            except (json.JSONDecodeError, KeyError):
                logger.error("OpenRouter HTTP %s (model=%s): %s", response.status_code, model, response.text[:300])
                response.raise_for_status()

        _check_body(response.json())
        return response

    response = await client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        try:
            body = response.json()
            err = body.get("error", {})
            _raise_openrouter_error(
                err.get("code", response.status_code),
                err.get("message", response.text[:300]),
                err.get("metadata"),
            )
        except (json.JSONDecodeError, KeyError):
            response.raise_for_status()
    _check_body(response.json())
    return response


# ── XML tool call parser ───────────────────────────────────────────────────────

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


# ── Response parser ────────────────────────────────────────────────────────────

def _parse_usage(data: dict) -> LLMUsage:
    u = data.get("usage", {})
    return LLMUsage(
        prompt_tokens=u.get("prompt_tokens", 0),
        completion_tokens=u.get("completion_tokens", 0),
        total_tokens=u.get("total_tokens", 0),
        reasoning_tokens=u.get("reasoning_tokens", 0),
        cached_tokens=u.get("cached_tokens", 0),
    )


def _parse_llm_response(data: dict) -> LLMResponse:
    choice = data["choices"][0]
    message = choice["message"]
    finish_reason = choice.get("finish_reason", "stop")

    usage = _parse_usage(data)

    # Reasoning — Kimi returns reasoning_details, others may return reasoning field
    reasoning_text: str | None = message.get("reasoning") or None
    reasoning_details: list[dict] = message.get("reasoning_details") or []

    # If reasoning_details present but no flat reasoning text, flatten it
    if reasoning_details and not reasoning_text:
        parts = [
            block.get("thinking") or block.get("text") or ""
            for block in reasoning_details
            if isinstance(block, dict)
        ]
        reasoning_text = "\n".join(p for p in parts if p) or None

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

    logger.debug(
        "OpenRouter response — finish_reason=%s tool_calls=%d reasoning_tokens=%d cached_tokens=%d",
        finish_reason, len(tool_calls), usage.reasoning_tokens, usage.cached_tokens,
    )

    if finish_reason == "length":
        logger.warning("OpenRouter response truncated — max_tokens reached (model=%s)", data.get("model", ""))

    return LLMResponse(
        content=content or None,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        reasoning=reasoning_text,
        reasoning_details=reasoning_details,
        usage=usage,
    )


# ── Provider ───────────────────────────────────────────────────────────────────

class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, base_url: str = "https://openrouter.ai/api/v1") -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._base_url = base_url
        llm_cfg = state.get_config().get("llm", {})
        self._request_timeout = float(llm_cfg.get("request_timeout", 120))
        self._tool_timeout = float(llm_cfg.get("tool_timeout", 300))
        self._max_retries = int(llm_cfg.get("max_retries", MAX_RETRIES))
        self._retry_base = int(llm_cfg.get("retry_base_seconds", RETRY_BASE_SECONDS))

    def name(self) -> str:
        return "openrouter"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thrall.ai",
            "X-Title": "Thrall",
        }

    def _routing_params(self) -> dict:
        """Build OpenRouter provider routing params from config [llm.routing]."""
        routing = state.get_config().get("llm", {}).get("routing", {})
        params: dict = {}

        fallbacks = routing.get("fallback_models", [])
        if fallbacks:
            params["models"] = fallbacks

        provider_opts: dict = {}
        for key in ("allow_fallbacks", "sort", "max_price", "only", "ignore", "require_parameters"):
            if key in routing:
                provider_opts[key] = routing[key]
        if provider_opts:
            params["provider"] = provider_opts

        return params

    def _base_payload(self, model: str, messages: list[dict], temperature: float, max_tokens: int) -> dict:
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload.update(self._routing_params())
        return payload

    async def complete(self, messages: list[dict], model: str, temperature: float, max_tokens: int) -> str:
        logger.debug("OpenRouter complete — model=%s messages=%d", model, len(messages))
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            payload = self._base_payload(model, messages, temperature, max_tokens)
            response = await _post_with_retry(client, f"{self._base_url}/chat/completions", self._headers(), payload, model, self._max_retries, self._retry_base)
            data = response.json()
            usage = _parse_usage(data)
            logger.debug("OpenRouter complete usage — total=%d reasoning=%d cached=%d", usage.total_tokens, usage.reasoning_tokens, usage.cached_tokens)
            return data["choices"][0]["message"]["content"]

    async def complete_with_tools(
        self, messages: list[dict], tools: list[dict], model: str, temperature: float, max_tokens: int,
    ) -> LLMResponse:
        logger.debug("OpenRouter complete_with_tools — model=%s messages=%d tools=%d", model, len(messages), len(tools))
        async with httpx.AsyncClient(timeout=self._tool_timeout) as client:
            payload = self._base_payload(model, messages, temperature, max_tokens)
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            response = await _post_with_retry(client, f"{self._base_url}/chat/completions", self._headers(), payload, model, self._max_retries, self._retry_base)
            return _parse_llm_response(response.json())

    async def stream(self, messages: list[dict], model: str, temperature: float, max_tokens: int) -> AsyncIterator[str]:
        logger.debug("OpenRouter stream — model=%s", model)
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            payload = self._base_payload(model, messages, temperature, max_tokens)
            payload["stream"] = True
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    try:
                        err = json.loads(body).get("error", {})
                        _raise_openrouter_error(
                            err.get("code", response.status_code),
                            err.get("message", body.decode()[:300]),
                            err.get("metadata"),
                        )
                    except (json.JSONDecodeError, KeyError):
                        response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    chunk = json.loads(line[6:])
                    if "error" in chunk:
                        err = chunk["error"]
                        _raise_openrouter_error(err.get("code", 0), err.get("message", str(err)))
                    choice = chunk["choices"][0] if chunk.get("choices") else {}
                    if choice.get("finish_reason") == "error":
                        logger.error("OpenRouter stream ended with finish_reason=error (model=%s)", model)
                        break
                    delta = choice.get("delta", {})
                    if content := delta.get("content"):
                        yield content
