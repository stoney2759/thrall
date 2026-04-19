from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    task_id_str = call.args.get("task_id", "")

    if not task_id_str:
        return _result(call.id, error="task_id is required", start=start)

    try:
        task_id = UUID(task_id_str)
    except ValueError:
        return _result(call.id, error=f"invalid task_id: {task_id_str}", start=start)

    from thrall.tasks.result_store import get_result
    entry = get_result(task_id)

    if entry is None:
        # Check if still running in pool
        from thrall.tasks import pool
        active_ids = [str(t.id) for t in pool.list_active()]
        if task_id_str in active_ids:
            return _result(call.id, output=f"status: running\ntask_id: {task_id_str}", start=start)
        return _result(call.id, error=f"no result found for task_id: {task_id_str}", start=start)

    lines = [f"status: {entry['status']}", f"task_id: {entry['task_id']}"]
    if entry.get("result"):
        lines.append(f"result:\n{entry['result']}")
    if entry.get("error"):
        lines.append(f"error: {entry['error']}")

    return _result(call.id, output="\n".join(lines), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "agents.result"
DESCRIPTION = "Get the result of a spawned agent by task_id. Returns status (running/done/failed) and output."
PARAMETERS = {
    "task_id": {"type": "string", "required": True},
}
