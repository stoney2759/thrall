from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    url = call.args.get("url", "").strip()
    wait_for = call.args.get("wait_for", "load")  # load | networkidle | domcontentloaded

    if not url:
        return _result(call.id, error="url is required", start=start)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        response = await page.goto(url, wait_until=wait_for, timeout=30_000)
        await page.wait_for_load_state("domcontentloaded")

        title = await page.title()
        current_url = page.url
        status = response.status if response else "?"

        return _result(call.id, output=f"Navigated to: {current_url}\nTitle: {title}\nStatus: {status}", start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser.navigate"
DESCRIPTION = "Navigate the browser to a URL. Returns page title and final URL after redirect. Call this first before any other browser tools."
PARAMETERS = {
    "url":      {"type": "string", "required": True},
    "wait_for": {"type": "string", "required": False, "default": "load"},
}
