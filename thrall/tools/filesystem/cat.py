from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from hooks.input_gate import sanitize_external
from thrall.tools.filesystem._resolve import resolve


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))

    try:
        if not path.exists():
            return _result(call.id, error=f"not found: {path}", start=start)
        if not path.is_file():
            return _result(call.id, error=f"not a file: {path}", start=start)

        content = path.read_text(encoding="utf-8", errors="replace")
        cleaned = sanitize_external(content)
        return _result(call.id, output=cleaned, start=start)
    except PermissionError:
        return _result(call.id, error=f"permission denied: {path}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "filesystem.cat"
DESCRIPTION = "Output full file contents without line numbers."
PARAMETERS = {
    "path": {"type": "string", "required": True},
}
