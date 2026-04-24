from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    value = call.args.get("value", "")
    label = call.args.get("label", "").strip()
    selector = call.args.get("selector", "").strip()
    submit = call.args.get("submit", False)

    if not label and not selector:
        return _result(call.id, error="provide either label or selector", start=start)

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        if label:
            # Try by label, placeholder, or aria-label
            locator = page.get_by_label(label, exact=False)
            count = await locator.count()
            if count == 0:
                locator = page.get_by_placeholder(label, exact=False)
                count = await locator.count()
            if count == 0:
                return _result(call.id, error=f"no input found with label/placeholder: {label!r}", start=start)
            await locator.first.fill(value, timeout=10_000)
        else:
            await page.fill(selector, value, timeout=10_000)

        if submit:
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
            title = await page.title()
            return _result(call.id, output=f"Filled and submitted. Now on: {page.url}\nTitle: {title}", start=start)

        return _result(call.id, output=f"Filled field {'label=' + repr(label) if label else 'selector=' + repr(selector)} with value.", start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser.fill"
DESCRIPTION = "Fill a form field on the current page. Use 'label' (visible field label or placeholder text) instead of 'selector' when possible. Set submit=true to press Enter after filling."
PARAMETERS = {
    "value":    {"type": "string",  "required": True},
    "label":    {"type": "string",  "required": False, "default": ""},
    "selector": {"type": "string",  "required": False, "default": ""},
    "submit":   {"type": "boolean", "required": False, "default": False},
}
