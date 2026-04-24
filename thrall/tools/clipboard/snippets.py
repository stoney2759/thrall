from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.clipboard._snippets import list_names, load_all, delete


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    action = call.args.get("action", "list").strip().lower()
    name = call.args.get("name", "").strip()

    if action == "delete":
        if not name:
            return _result(call.id, error="name is required for delete", start=start)
        removed = delete(name)
        if not removed:
            return _result(call.id, error=f"no snippet named '{name}'", start=start)
        return _result(call.id, output=f"deleted snippet '{name}'", start=start)

    names = list_names()
    if not names:
        return _result(call.id, output="no saved snippets yet", start=start)

    all_snippets = load_all()
    lines = []
    for n in names:
        preview = all_snippets[n][:60].replace("\n", " ")
        lines.append(f"• {n} — {preview}{'…' if len(all_snippets[n]) > 60 else ''}")

    return _result(call.id, output="\n".join(lines), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "clipboard.snippets"
DESCRIPTION = "List all saved snippets with a preview, or delete one by name."
PARAMETERS = {
    "action": {"type": "string", "required": False, "default": "list"},
    "name":   {"type": "string", "required": False, "default": ""},
}
