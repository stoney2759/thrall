from __future__ import annotations
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected
import time


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))
    content = call.args.get("content", "")
    newline = call.args.get("newline", True)

    try:
        if is_protected(path):
            return _result(call.id, error=f"path not found: {path}", start=start)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            if newline and path.stat().st_size > 0 if path.exists() else False:
                f.write("\n")
            f.write(content)
        return _result(call.id, output=f"appended to: {path}", start=start)
    except PermissionError:
        return _result(call.id, error=f"permission denied: {path}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "filesystem.append"
DESCRIPTION = "Append content to a file. Creates the file if it does not exist. Adds a newline before content if the file already has content."
PARAMETERS = {
    "path": {"type": "string", "required": True},
    "content": {"type": "string", "required": True},
    "newline": {"type": "boolean", "required": False, "default": True},
}
