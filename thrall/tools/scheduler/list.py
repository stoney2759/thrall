from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    from scheduler import store

    jobs = store.load_jobs()
    if not jobs:
        return _result(call.id, output="No scheduled jobs.", start=start)

    lines = [f"Scheduled jobs ({len(jobs)}):"]
    for j in jobs:
        status = "enabled" if j.enabled else "disabled"
        agent = f" agent={j.agent}" if j.agent else ""
        lines.append(f"  [{j.id}] {j.type} {j.schedule_summary()}{agent} | {status} | {j.output_mode}")
        lines.append(f"    Task: {j.task[:100]}")
        if j.last_run:
            lines.append(f"    Last run: {j.last_run[:19]}")

    return _result(call.id, output="\n".join(lines), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "scheduler_list"
DESCRIPTION = "List all scheduled heartbeat and cron jobs."
PARAMETERS = {}
