from __future__ import annotations
import re
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected

_MAX_RESULTS = 200


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    root = resolve(call.args.get("path", "."))
    name_pattern = call.args.get("name", "")
    kind = call.args.get("type", "any")          # "file" | "dir" | "any"
    min_size = call.args.get("min_size", None)    # bytes
    max_size = call.args.get("max_size", None)    # bytes
    extension = call.args.get("extension", "")   # e.g. ".py"
    limit = call.args.get("limit", _MAX_RESULTS)

    try:
        name_re = re.compile(name_pattern, re.IGNORECASE) if name_pattern else None
        results: list[str] = []

        for entry in root.rglob("*"):
            if len(results) >= limit:
                break
            try:
                if kind == "file" and not entry.is_file():
                    continue
                if kind == "dir" and not entry.is_dir():
                    continue
                if name_re and not name_re.search(entry.name):
                    continue
                if extension and entry.suffix.lower() != extension.lower():
                    continue
                if entry.is_file() and (min_size is not None or max_size is not None):
                    size = entry.stat().st_size
                    if min_size is not None and size < min_size:
                        continue
                    if max_size is not None and size > max_size:
                        continue
                if not is_protected(entry):
                    results.append(str(entry))
            except (PermissionError, OSError):
                continue

        output = "\n".join(results) if results else "no matches"
        if len(results) >= limit:
            output += f"\n... (limited to {limit} results)"
        return _result(call.id, output=output, start=start)

    except re.error as e:
        return _result(call.id, error=f"invalid name pattern: {e}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "filesystem_find"
DESCRIPTION = "Find files and directories by name pattern, type, size, or extension."
PARAMETERS = {
    "path": {"type": "string", "required": False, "default": "."},
    "name": {"type": "string", "required": False, "default": ""},
    "type": {"type": "string", "required": False, "default": "any"},
    "extension": {"type": "string", "required": False, "default": ""},
    "min_size": {"type": "integer", "required": False},
    "max_size": {"type": "integer", "required": False},
    "limit": {"type": "integer", "required": False, "default": 200},
}
