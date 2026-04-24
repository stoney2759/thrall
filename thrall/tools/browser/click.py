from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    text = call.args.get("text", "").strip()
    selector = call.args.get("selector", "").strip()

    if not text and not selector:
        return _result(call.id, error="provide either text or selector", start=start)

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        if text:
            # Try exact text match first, then partial
            locator = page.get_by_text(text, exact=True)
            count = await locator.count()
            if count == 0:
                locator = page.get_by_text(text, exact=False)
                count = await locator.count()
            if count == 0:
                # Try role-based: button, link, etc.
                locator = page.get_by_role("button", name=text)
                count = await locator.count()
            if count == 0:
                locator = page.get_by_role("link", name=text)
                count = await locator.count()
            if count == 0:
                return _result(call.id, error=f"no element found with text: {text!r}", start=start)
            await locator.first.click(timeout=10_000)
        else:
            await page.click(selector, timeout=10_000)

        await page.wait_for_load_state("domcontentloaded", timeout=10_000)
        title = await page.title()
        current_url = page.url

        return _result(call.id, output=f"Clicked. Now on: {current_url}\nTitle: {title}", start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser.click"
DESCRIPTION = "Click an element on the current page. Prefer using 'text' (the visible label or button text) over 'selector'. After clicking, returns the new page URL and title."
PARAMETERS = {
    "text":     {"type": "string", "required": False, "default": ""},
    "selector": {"type": "string", "required": False, "default": ""},
}
