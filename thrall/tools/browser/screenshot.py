from __future__ import annotations
import time
from pathlib import Path
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult
from constants.tools import SCREENSHOT_SAVE_EXTS
from thrall.tools.filesystem._resolve import resolve


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    prompt = call.args.get("prompt", "").strip()
    save_path = call.args.get("save_path", "").strip()

    target: Path | None = None
    if save_path:
        target, error = _save_target(save_path)
        if error:
            return _result(call.id, error=error, start=start)

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        image_bytes = await page.screenshot(type="jpeg", quality=80, full_page=False)
        current_url = page.url
        title = await page.title()

        saved_note = ""
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            image_type = "png" if target.suffix.lower() == ".png" else "jpeg"
            await page.screenshot(path=str(target), type=image_type, full_page=False)
            saved_note = f"\nSaved to: {target}"

        from services.vision.openai import describe
        vision_prompt = prompt or (
            "You are looking at a browser screenshot. "
            "Describe the page layout, main content, visible text, buttons, forms, and any interactive elements. "
            "Be specific — include exact button labels, link text, form field labels, and any error or status messages."
        )
        description = await describe(image_bytes, media_type="image/jpeg", prompt=vision_prompt)

        output = f"[Browser screenshot — {title} | {current_url}]{saved_note}\n\n{description}"
        return _result(call.id, output=output, start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _save_target(save_path: str) -> tuple[Path | None, str | None]:
    """A screenshot is a read-only tool, so saving is limited to a NEW image file inside the workspace."""
    target = resolve(save_path)
    if target.suffix.lower() not in SCREENSHOT_SAVE_EXTS:
        return None, f"save_path must end in one of: {', '.join(sorted(SCREENSHOT_SAVE_EXTS))}"
    workspace = state.get_workspace_dir()
    if not workspace or not target.resolve().is_relative_to(Path(workspace).resolve()):
        return None, "save_path must be inside the workspace"
    if target.exists():
        return None, f"file already exists: {target} — choose a new name"
    return target, None


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser_screenshot"
DESCRIPTION = "Take a screenshot of the current browser page and return a visual description. Use this to understand the current page state before clicking or filling forms. Pass save_path to also save the image as a new .png/.jpg file in the workspace."
PARAMETERS = {
    "prompt": {"type": "string", "required": False, "default": ""},
    "save_path": {"type": "string", "required": False, "default": "", "description": "Optional new .png or .jpg file to save the screenshot to (inside the workspace; existing files are not overwritten)."},
}
