from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    text = call.args.get("text", "")
    append = call.args.get("append", False)

    if not text:
        return _result(call.id, error="text is required", start=start)

    try:
        import win32clipboard
        if append:
            win32clipboard.OpenClipboard()
            try:
                existing = ""
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    existing = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
            text = existing + text

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()
    except ImportError:
        try:
            import pyperclip
            if append:
                text = pyperclip.paste() + text
            pyperclip.copy(text)
        except Exception as e:
            return _result(call.id, error=f"clipboard write failed: {e}", start=start)
    except Exception as e:
        return _result(call.id, error=f"clipboard write failed: {e}", start=start)

    return _result(call.id, output=f"copied to clipboard ({len(text)} chars)", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "clipboard.write"
DESCRIPTION = "Write text to the system clipboard. Use append=true to add to existing content rather than replace it."
PARAMETERS = {
    "text":   {"type": "string",  "required": True},
    "append": {"type": "boolean", "required": False, "default": False},
}
