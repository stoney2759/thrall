from __future__ import annotations
import os
import time
from uuid import UUID
import httpx
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    query = call.args.get("query", "")
    limit = call.args.get("limit", 10)

    api_key = os.environ.get("BRAVE_API_KEY") or os.environ.get("SERPER_API_KEY")

    if os.environ.get("BRAVE_API_KEY"):
        return await _brave(call.id, query, limit, start)
    if os.environ.get("SERPER_API_KEY"):
        return await _serper(call.id, query, limit, start)

    return _result(call.id, error="no search API key configured (BRAVE_API_KEY or SERPER_API_KEY)", start=start)


async def _brave(call_id: UUID, query: str, limit: int, start: float) -> ToolResult:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": os.environ["BRAVE_API_KEY"]},
                params={"q": query, "count": limit},
            )
            response.raise_for_status()
            results = response.json().get("web", {}).get("results", [])
            output = "\n\n".join(
                f"[{r.get('title')}]\n{r.get('url')}\n{r.get('description', '')}"
                for r in results
            )
            return _result(call_id, output=output or "no results", start=start)
    except Exception as e:
        return _result(call_id, error=str(e), start=start)


async def _serper(call_id: UUID, query: str, limit: int, start: float) -> ToolResult:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"},
                json={"q": query, "num": limit},
            )
            response.raise_for_status()
            results = response.json().get("organic", [])
            output = "\n\n".join(
                f"[{r.get('title')}]\n{r.get('link')}\n{r.get('snippet', '')}"
                for r in results
            )
            return _result(call_id, output=output or "no results", start=start)
    except Exception as e:
        return _result(call_id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "web.search"
DESCRIPTION = "Search the web. Requires BRAVE_API_KEY or SERPER_API_KEY."
PARAMETERS = {
    "query": {"type": "string", "required": True},
    "limit": {"type": "integer", "required": False, "default": 10},
}
