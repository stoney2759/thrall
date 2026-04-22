from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, filter_protected


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", "."))
    show_hidden = call.args.get("hidden", False)

    try:
        if not path.exists():
            return _result(call.id, error=f"not found: {path}", start=start)
        if not path.is_dir():
            return _result(call.id, error=f"not a directory: {path}", start=start)

        entries = filter_protected(sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())))
        lines = []
        for entry in entries:
            if not show_hidden and entry.name.startswith("."):
                continue
            kind = "/" if entry.is_dir() else ""
            try:
                size = entry.stat().st_size if entry.is_file() else ""
                size_str = f"  {_human(size)}" if size != "" else ""
            except Exception:
                size_str = ""
            lines.append(f"{entry.name}{kind}{size_str}")

        return _result(call.id, output="\n".join(lines) or "(empty)", start=start)
    except PermissionError:
        return _result(call.id, error=f"permission denied: {path}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size}{unit}"
        size //= 1024
    return f"{size}TB"


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "filesystem.ls"
DESCRIPTION = "List directory contents with type and size."
PARAMETERS = {
    "path": {"type": "string", "required": False, "default": "."},
    "hidden": {"type": "boolean", "required": False, "default": False},
}
