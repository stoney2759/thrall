from __future__ import annotations
import re
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected
import time


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    pattern = call.args.get("pattern", "")
    root = resolve(call.args.get("path", "."))
    glob_filter = call.args.get("glob", "**/*")
    case_insensitive = call.args.get("case_insensitive", False)
    context_lines = call.args.get("context", 0)
    limit = call.args.get("limit", 100)

    try:
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)
        results: list[str] = []

        for path in root.glob(glob_filter):
            if not path.is_file() or is_protected(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines):
                if regex.search(line):
                    block = [f"{path}:{i + 1}: {line}"]
                    if context_lines:
                        before = lines[max(0, i - context_lines): i]
                        after = lines[i + 1: i + 1 + context_lines]
                        block = [f"{path}:{j + 1}-: {l}" for j, l in enumerate(before, max(0, i - context_lines))] + block
                        block += [f"{path}:{j + 1}+: {l}" for j, l in enumerate(after, i + 1)]
                    results.extend(block)

                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

        output = "\n".join(results[:limit]) if results else "no matches"
        return _result(call.id, output=output, start=start)
    except re.error as e:
        return _result(call.id, error=f"invalid regex: {e}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(
        call_id=call_id,
        output=output,
        error=error,
        duration_ms=int((time.monotonic() - start) * 1000),
    )


NAME = "filesystem.grep"
DESCRIPTION = "Search file contents using regex. Returns matching lines with file path and line number."
PARAMETERS = {
    "pattern": {"type": "string", "required": True},
    "path": {"type": "string", "required": False, "default": "."},
    "glob": {"type": "string", "required": False, "default": "**/*"},
    "case_insensitive": {"type": "boolean", "required": False, "default": False},
    "context": {"type": "integer", "required": False, "default": 0},
    "limit": {"type": "integer", "required": False, "default": 100},
}
