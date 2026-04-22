from __future__ import annotations
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from hooks import input_gate
from thrall.tools.filesystem._resolve import resolve, is_protected
import time


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))

    try:
        if is_protected(path) or not path.exists():
            return _result(call.id, error=f"path not found: {path}", start=start)
        if not path.is_file():
            return _result(call.id, error=f"not a file: {path}", start=start)

        offset = call.args.get("offset", 0)
        limit = call.args.get("limit", 2000)

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[offset: offset + limit]
        numbered = "\n".join(f"{offset + i + 1}\t{line}" for i, line in enumerate(selected))

        # Sanitize external file content before returning to Thrall
        cleaned = input_gate.sanitize_external(numbered)
        return _result(call.id, output=cleaned, start=start)

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


NAME = "filesystem.read"
DESCRIPTION = "Read a file from the filesystem. Returns numbered lines."
PARAMETERS = {
    "path": {"type": "string", "required": True},
    "offset": {"type": "integer", "required": False, "default": 0},
    "limit": {"type": "integer", "required": False, "default": 2000},
}
