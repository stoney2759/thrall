from __future__ import annotations
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected
import time


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))
    content = call.args.get("content", "")

    try:
        if is_protected(path):
            return _result(call.id, error=f"path not found: {path}", start=start)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return _result(call.id, output=f"written: {path}", start=start)
    except PermissionError:
        return _result(call.id, error=f"permission denied: {path}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(
        call_id=call_id,
        output=output,
        error=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


NAME = "filesystem.write"
DESCRIPTION = "Write content to a file. Creates parent directories if needed."
PARAMETERS = {
    "path": {"type": "string", "required": True},
    "content": {"type": "string", "required": True},
}
