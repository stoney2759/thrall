from __future__ import annotations
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve
import time


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))
    old = call.args.get("old_string", "")
    new = call.args.get("new_string", "")
    replace_all = call.args.get("replace_all", False)

    try:
        if not path.exists():
            return _result(call.id, error=f"file not found: {path}", start=start)

        content = path.read_text(encoding="utf-8")

        if old not in content:
            return _result(call.id, error="old_string not found in file", start=start)

        count = content.count(old)
        if count > 1 and not replace_all:
            return _result(
                call.id,
                error=f"old_string appears {count} times — set replace_all=true or provide more context",
                start=start,
            )

        updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
        path.write_text(updated, encoding="utf-8")
        replacements = count if replace_all else 1
        return _result(call.id, output=f"replaced {replacements} occurrence(s) in {path}", start=start)

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


NAME = "filesystem.edit"
DESCRIPTION = "Replace a string in a file. Exact match required."
PARAMETERS = {
    "path": {"type": "string", "required": True},
    "old_string": {"type": "string", "required": True},
    "new_string": {"type": "string", "required": True},
    "replace_all": {"type": "boolean", "required": False, "default": False},
}
