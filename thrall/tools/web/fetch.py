from __future__ import annotations
import time
from uuid import UUID
import httpx
from schemas.tool import ToolCall, ToolResult
from hooks.input_gate import sanitize_external


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    url = call.args.get("url", "")
    timeout = call.args.get("timeout", 30)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Thrall/2.0"})
            response.raise_for_status()
            content = sanitize_external(response.text)
            return _result(call.id, output=content, start=start)
    except httpx.HTTPStatusError as e:
        return _result(call.id, error=f"HTTP {e.response.status_code}: {url}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "web.fetch"
DESCRIPTION = "Fetch raw content from a URL."
PARAMETERS = {
    "url": {"type": "string", "required": True},
    "timeout": {"type": "integer", "required": False, "default": 30},
}
