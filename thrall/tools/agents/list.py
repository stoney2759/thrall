from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()

    from thrall.tasks import pool
    from thrall.tasks.result_store import all_results

    active = pool.list_active()
    completed = all_results()

    lines = []

    if active:
        lines.append(f"Running ({len(active)}):")
        for t in active:
            lines.append(f"  {t.id} — {t.brief[:60]}")
    else:
        lines.append("Running: none")

    if completed:
        lines.append(f"\nCompleted ({len(completed)}):")
        for r in completed[-10:]:
            lines.append(f"  {r['task_id']} [{r['status']}]")
    else:
        lines.append("Completed: none")

    return _result(call.id, output="\n".join(lines), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "agents.list"
DESCRIPTION = "List all running and recently completed agents with their status."
PARAMETERS = {}
