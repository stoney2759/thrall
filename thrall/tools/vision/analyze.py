from __future__ import annotations
import mimetypes
import os
import time
from pathlib import Path
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    file_path = call.args.get("file_path", "").strip()
    prompt = call.args.get("prompt", "")

    if not file_path:
        return _result(call.id, error="file_path is required", start=start)

    workspace_dir = state.get_workspace_dir()
    if workspace_dir and not os.path.isabs(file_path):
        file_path = os.path.join(workspace_dir, file_path)

    if not os.path.exists(file_path):
        return _result(call.id, error=f"file not found: {file_path}", start=start)

    media_type, _ = mimetypes.guess_type(file_path)
    if not media_type or not media_type.startswith("image/"):
        media_type = "image/jpeg"

    image_bytes = Path(file_path).read_bytes()

    from services.vision.openai import describe
    try:
        description = await describe(image_bytes, media_type=media_type, prompt=prompt)
    except Exception as e:
        return _result(call.id, error=f"vision analysis failed: {e}", start=start)

    return _result(call.id, output=description, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "vision_analyze"
DESCRIPTION = "Analyze an image file using the vision model. Returns a detailed description of what is shown. Use for frame-by-frame visual context of video content."
PARAMETERS = {
    "file_path": {
        "type": "string",
        "required": True,
        "description": "Path to the image file (jpg, png, webp). Relative paths resolve to workspace.",
    },
    "prompt": {
        "type": "string",
        "required": False,
        "description": "Custom prompt for the vision model. Default: describe the image in detail and transcribe any visible text.",
    },
}
