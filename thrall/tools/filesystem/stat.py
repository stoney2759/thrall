from __future__ import annotations
import time
from datetime import datetime, timezone
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))

    try:
        if not path.exists():
            return _result(call.id, error=f"not found: {path}", start=start)

        s = path.stat()
        kind = "directory" if path.is_dir() else "file"
        modified = datetime.fromtimestamp(s.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        created = datetime.fromtimestamp(s.st_ctime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            f"path:     {path.resolve()}",
            f"type:     {kind}",
            f"size:     {_human(s.st_size)}",
            f"modified: {modified}",
            f"created:  {created}",
            f"mode:     {oct(s.st_mode)}",
        ]
        if path.is_file():
            lines.append(f"suffix:   {path.suffix or '(none)'}")

        return _result(call.id, output="\n".join(lines), start=start)
    except PermissionError:
        return _result(call.id, error=f"permission denied: {path}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size} {unit}"
        size //= 1024
    return f"{size} TB"


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "filesystem.stat"
DESCRIPTION = "Get file or directory metadata: size, type, timestamps, permissions."
PARAMETERS = {
    "path": {"type": "string", "required": True},
}
