from __future__ import annotations
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected
from constants.tools import CODE_EXTS
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
        msg = f"written: {path}\n[Verify with filesystem_ls before reporting completion."
        if path.suffix in CODE_EXTS:
            msg += " This is a code file — re-read it and check for: string interpolation in shell/subprocess calls, hardcoded paths, argument escaping, and logic errors before reporting done."
        msg += "]"
        return _result(call.id, output=msg, start=start)
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


NAME = "filesystem_write"
DESCRIPTION = "Write content to a file. Creates parent directories if needed."
PARAMETERS = {
    "path": {"type": "string", "required": True},
    "content": {"type": "string", "required": True},
}
