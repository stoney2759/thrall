from __future__ import annotations
import time
from uuid import UUID
from schemas.memory import TodoItem, TodoStatus
from schemas.tool import ToolCall, ToolResult
from services import session_memory
from constants.tools import TODO_MAX_ITEMS

_MARKS: dict[TodoStatus, str] = {
    TodoStatus.PENDING: "[ ]",
    TodoStatus.IN_PROGRESS: "[~]",
    TodoStatus.DONE: "[x]",
}


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    raw = call.args.get("items")
    if not isinstance(raw, list) or not raw:
        return _result(call.id, start, error="items is required — a list of {content, status}")
    if len(raw) > TODO_MAX_ITEMS:
        return _result(call.id, start, error=f"too many items ({len(raw)}) — max {TODO_MAX_ITEMS}; group steps")

    items: list[TodoItem] = []
    valid = ", ".join(s.value for s in TodoStatus)
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict) or not str(entry.get("content", "")).strip():
            return _result(call.id, start, error=f"item {i + 1} needs a non-empty 'content'")
        status = str(entry.get("status", TodoStatus.PENDING.value))
        if status not in {s.value for s in TodoStatus}:
            return _result(call.id, start, error=f"item {i + 1} has status '{status}' — use one of: {valid}")
        items.append(TodoItem(content=str(entry["content"]).strip(), status=TodoStatus(status)))

    session_memory.set_todos(call.session_id, items)
    return _result(call.id, start, output=render(items))


def render(items: list[TodoItem]) -> str:
    done = sum(1 for t in items if t.status == TodoStatus.DONE)
    lines = [f"Checklist ({done}/{len(items)} done):"]
    lines.extend(f"{_MARKS[t.status]} {t.content}" for t in items)
    return "\n".join(lines)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "todo_write"
DESCRIPTION = (
    "Keep a checklist for multi-step work (3+ steps). Send the FULL list every call — it replaces the "
    "previous one. Mark one item in_progress while you work on it and done as soon as it is finished. "
    "You cannot give a final 'done' reply while items are still pending or in_progress — finish them, "
    "or remove them and tell the user why."
)
PARAMETERS = {
    "items": {
        "type": "array",
        "required": True,
        "items": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
            },
            "required": ["content", "status"],
        },
    },
}
