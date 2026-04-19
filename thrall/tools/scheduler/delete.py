from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    job_id = call.args.get("id", "").strip()
    if not job_id:
        return _result(call.id, error="id is required", start=start)

    from scheduler import store
    deleted = store.delete_job(job_id)
    if deleted:
        return _result(call.id, output=f"Job `{job_id}` deleted.", start=start)
    return _result(call.id, error=f"No job found with id '{job_id}'.", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "scheduler.delete"
DESCRIPTION = "Delete a scheduled job by its ID."
PARAMETERS = {
    "id": {"type": "string", "required": True},
}
