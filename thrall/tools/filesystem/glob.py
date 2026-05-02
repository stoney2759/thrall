from __future__ import annotations
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected, filter_protected
import time


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    pattern = call.args.get("pattern", "**/*")
    root = resolve(call.args.get("path", "."))
    limit = call.args.get("limit", 500)

    try:
        matches = filter_protected(sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True))
        paths = [str(p) for p in matches[:limit]]
        output = "\n".join(paths) if paths else "no matches"
        return _result(call.id, output=output, start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(
        call_id=call_id,
        output=output,
        error=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


NAME = "filesystem_glob"
DESCRIPTION = "Find files matching a glob pattern, sorted by modification time."
PARAMETERS = {
    "pattern": {"type": "string", "required": True},
    "path": {"type": "string", "required": False, "default": "."},
    "limit": {"type": "integer", "required": False, "default": 500},
}
