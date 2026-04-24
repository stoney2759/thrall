from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.clipboard._snippets import get


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    name = call.args.get("name", "").strip()
    push = call.args.get("push_to_clipboard", True)

    if not name:
        return _result(call.id, error="name is required", start=start)

    content = get(name)
    if content is None:
        return _result(call.id, error=f"no snippet named '{name}'", start=start)

    if push:
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, content)
            finally:
                win32clipboard.CloseClipboard()
        except ImportError:
            try:
                import pyperclip
                pyperclip.copy(content)
            except Exception:
                pass
        except Exception:
            pass

    return _result(call.id, output=content, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "clipboard.load"
DESCRIPTION = "Recall a saved snippet by name. Also copies it to the system clipboard by default so the user can paste immediately."
PARAMETERS = {
    "name":               {"type": "string",  "required": True},
    "push_to_clipboard":  {"type": "boolean", "required": False, "default": True},
}
