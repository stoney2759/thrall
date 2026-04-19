from __future__ import annotations
import re
import time
import uuid
from datetime import datetime, timezone
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


def _detect_type(schedule: str) -> str | None:
    if re.fullmatch(r"\d+[smhd]", schedule.strip().lower()):
        return "heartbeat"
    if re.fullmatch(r"\d{1,2}:\d{2}", schedule.strip()):
        return "cron"
    return None


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    schedule = call.args.get("schedule", "").strip()
    task = call.args.get("task", "").strip()
    agent = call.args.get("agent") or None
    output_mode = call.args.get("output_mode", "verbose")
    job_type = call.args.get("type", "").strip() or _detect_type(schedule)

    if not schedule:
        return _result(call.id, error="schedule is required (e.g. '30m', '2h', '1d', '18:00')", start=start)
    if not task:
        return _result(call.id, error="task is required", start=start)
    if job_type is None:
        return _result(call.id, error=f"could not detect job type from schedule '{schedule}'", start=start)
    if output_mode not in ("verbose", "silent"):
        output_mode = "verbose"

    from scheduler.job import Job
    from scheduler import store

    job = Job(
        id=uuid.uuid4().hex[:8],
        type=job_type,
        schedule=schedule,
        task=task,
        agent=agent,
        output_mode=output_mode,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    store.add_job(job)

    return _result(
        call.id,
        output=f"Job `{job.id}` scheduled ({job.schedule_summary()}): {task[:80]}",
        start=start,
    )


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "scheduler.add"
DESCRIPTION = "Add a scheduled job. Use type='heartbeat' for recurring (schedule='30m'/'2h'/'1d') or type='cron' for daily at a time (schedule='18:00'). Optionally specify an agent from the catalog."
PARAMETERS = {
    "schedule": {"type": "string", "required": True},
    "task": {"type": "string", "required": True},
    "type": {"type": "string", "required": False, "default": ""},
    "agent": {"type": "string", "required": False, "default": ""},
    "output_mode": {"type": "string", "required": False, "default": "verbose"},
}
