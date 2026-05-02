from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected

_MAX_ENTRIES = 500


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", "."))
    max_depth = call.args.get("max_depth", 4)
    show_hidden = call.args.get("hidden", False)

    try:
        if not path.exists():
            return _result(call.id, error=f"not found: {path}", start=start)

        lines: list[str] = [str(path)]
        count = [0]
        _walk(path, "", max_depth, 0, show_hidden, lines, count)

        if count[0] >= _MAX_ENTRIES:
            lines.append(f"... (truncated at {_MAX_ENTRIES} entries)")

        return _result(call.id, output="\n".join(lines), start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _walk(path: Path, prefix: str, max_depth: int, depth: int, hidden: bool, lines: list, count: list) -> None:
    if depth >= max_depth or count[0] >= _MAX_ENTRIES:
        return
    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return

    visible = [e for e in entries if hidden or not e.name.startswith(".")]
    visible = [e for e in visible if not is_protected(e)]
    for i, entry in enumerate(visible):
        if count[0] >= _MAX_ENTRIES:
            break
        is_last = i == len(visible) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
        count[0] += 1
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            _walk(entry, prefix + extension, max_depth, depth + 1, hidden, lines, count)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "filesystem_tree"
DESCRIPTION = "Display directory structure as a tree."
PARAMETERS = {
    "path": {"type": "string", "required": False, "default": "."},
    "max_depth": {"type": "integer", "required": False, "default": 4},
    "hidden": {"type": "boolean", "required": False, "default": False},
}
