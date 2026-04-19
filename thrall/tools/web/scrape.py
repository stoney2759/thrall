from __future__ import annotations
import re
import time
from uuid import UUID
import httpx
from schemas.tool import ToolCall, ToolResult
from hooks.input_gate import sanitize_external


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\n{3,}")


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    url = call.args.get("url", "")
    timeout = call.args.get("timeout", 30)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Thrall/2.0"})
            response.raise_for_status()
            text = _extract_text(response.text)
            cleaned = sanitize_external(text)
            return _result(call.id, output=cleaned, start=start)
    except httpx.HTTPStatusError as e:
        return _result(call.id, error=f"HTTP {e.response.status_code}: {url}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _extract_text(html: str) -> str:
    # Strip scripts and styles first
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = _TAG_RE.sub(" ", html)
    text = _WHITESPACE_RE.sub("\n\n", text)
    return text.strip()


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "web.scrape"
DESCRIPTION = "Fetch a URL and extract readable text, stripping HTML tags."
PARAMETERS = {
    "url": {"type": "string", "required": True},
    "timeout": {"type": "integer", "required": False, "default": 30},
}
