from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.clipboard._snippets import save


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    name = call.args.get("name", "").strip()
    content = call.args.get("content", "")

    if not name:
        return _result(call.id, error="name is required", start=start)
    if not content:
        return _result(call.id, error="content is required", start=start)

    try:
        save(name, content)
    except Exception as e:
        return _result(call.id, error=f"failed to save snippet: {e}", start=start)

    return _result(call.id, output=f"saved snippet '{name}' ({len(content)} chars)", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "clipboard_save"
DESCRIPTION = "Save a named snippet for later recall. Use this to store frequently used text, templates, or variables that the user wants to reuse."
PARAMETERS = {
    "name":    {"type": "string", "required": True},
    "content": {"type": "string", "required": True},
}
