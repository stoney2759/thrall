from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.clipboard._detect import detect_type


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                text = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT).decode("utf-8", errors="replace")
            else:
                return _result(call.id, error="clipboard is empty or contains non-text content", start=start)
        finally:
            win32clipboard.CloseClipboard()
    except ImportError:
        try:
            import pyperclip
            text = pyperclip.paste()
        except Exception as e:
            return _result(call.id, error=f"clipboard read failed: {e}", start=start)
    except Exception as e:
        return _result(call.id, error=f"clipboard read failed: {e}", start=start)

    content_type = detect_type(text)
    return _result(call.id, output=f"[type: {content_type}]\n{text}", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "clipboard_read"
DESCRIPTION = "Read the current contents of the system clipboard. Returns content with detected type (url, file_path, code, html, text)."
PARAMETERS = {}
