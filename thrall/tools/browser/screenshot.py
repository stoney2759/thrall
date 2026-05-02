from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    prompt = call.args.get("prompt", "").strip()

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        image_bytes = await page.screenshot(type="jpeg", quality=80, full_page=False)
        current_url = page.url
        title = await page.title()

        from services.vision.openai import describe
        vision_prompt = prompt or (
            "You are looking at a browser screenshot. "
            "Describe the page layout, main content, visible text, buttons, forms, and any interactive elements. "
            "Be specific — include exact button labels, link text, form field labels, and any error or status messages."
        )
        description = await describe(image_bytes, media_type="image/jpeg", prompt=vision_prompt)

        output = f"[Browser screenshot — {title} | {current_url}]\n\n{description}"
        return _result(call.id, output=output, start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser_screenshot"
DESCRIPTION = "Take a screenshot of the current browser page and return a visual description. Use this to understand the current page state before clicking or filling forms."
PARAMETERS = {
    "prompt": {"type": "string", "required": False, "default": ""},
}
