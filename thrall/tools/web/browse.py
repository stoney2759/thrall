from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from hooks.input_gate import sanitize_external


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    url = call.args.get("url", "")
    wait_for = call.args.get("wait_for", "networkidle")
    timeout = call.args.get("timeout", 30000)

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until=wait_for, timeout=timeout)
            content = await page.inner_text("body")
            await browser.close()
            cleaned = sanitize_external(content)
            return _result(call.id, output=cleaned, start=start)
    except ImportError:
        return _result(call.id, error="playwright not installed — run: playwright install chromium", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "web_browse"
DESCRIPTION = "Browse a URL using a headless browser (JavaScript rendered). Requires playwright."
PARAMETERS = {
    "url": {"type": "string", "required": True},
    "wait_for": {"type": "string", "required": False, "default": "networkidle"},
    "timeout": {"type": "integer", "required": False, "default": 30000},
}
