from __future__ import annotations
import difflib
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path_a = call.args.get("path_a", "")
    path_b = call.args.get("path_b", "")
    text_a = call.args.get("text_a", "")
    text_b = call.args.get("text_b", "")
    context = call.args.get("context", 3)

    try:
        if path_a and path_b:
            a_lines = resolve(path_a).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            b_lines = resolve(path_b).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            label_a, label_b = path_a, path_b
        elif text_a and text_b:
            a_lines = (text_a + "\n").splitlines(keepends=True)
            b_lines = (text_b + "\n").splitlines(keepends=True)
            label_a, label_b = "a", "b"
        else:
            return _result(call.id, error="provide path_a+path_b or text_a+text_b", start=start)

        diff = list(difflib.unified_diff(a_lines, b_lines, fromfile=label_a, tofile=label_b, n=context))
        output = "".join(diff) if diff else "no differences"
        return _result(call.id, output=output, start=start)

    except FileNotFoundError as e:
        return _result(call.id, error=str(e), start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "filesystem.diff"
DESCRIPTION = "Diff two files or two text strings. Returns unified diff format."
PARAMETERS = {
    "path_a": {"type": "string", "required": False},
    "path_b": {"type": "string", "required": False},
    "text_a": {"type": "string", "required": False},
    "text_b": {"type": "string", "required": False},
    "context": {"type": "integer", "required": False, "default": 3},
}
