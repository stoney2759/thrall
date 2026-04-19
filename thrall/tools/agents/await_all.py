from __future__ import annotations
import asyncio
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

_POLL_INTERVAL = 2.0  # seconds between checks
_DEFAULT_TIMEOUT = 120  # seconds


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    task_ids_raw = call.args.get("task_ids", [])
    timeout = call.args.get("timeout", _DEFAULT_TIMEOUT)

    if not task_ids_raw:
        return _result(call.id, error="task_ids is required", start=start)

    try:
        task_ids = [UUID(tid) for tid in task_ids_raw]
    except ValueError as e:
        return _result(call.id, error=f"invalid task_id: {e}", start=start)

    from thrall.tasks.result_store import get_result
    from thrall.tasks import pool

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        active_ids = {t.id for t in pool.list_active()}
        pending = [tid for tid in task_ids if tid in active_ids]

        if not pending:
            break

        await asyncio.sleep(_POLL_INTERVAL)

    # Collect all results
    lines = []
    for tid in task_ids:
        entry = get_result(tid)
        if entry:
            lines.append(f"--- Agent {tid} [{entry['status']}] ---")
            if entry.get("result"):
                lines.append(entry["result"])
            if entry.get("error"):
                lines.append(f"error: {entry['error']}")
        else:
            lines.append(f"--- Agent {tid} [timeout or missing] ---")

    return _result(call.id, output="\n".join(lines) or "no results", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "agents.await_all"
DESCRIPTION = "Wait for multiple agents to complete and return all their results. Polls until done or timeout."
PARAMETERS = {
    "task_ids": {"type": "array", "required": True},
    "timeout": {"type": "integer", "required": False, "default": 120},
}
