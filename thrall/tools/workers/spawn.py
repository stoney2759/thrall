from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from schemas.task import Task, TaskType, CapabilityProfile
from bootstrap import state


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    brief = call.args.get("brief", "")
    task_type = call.args.get("type", "local")
    profile_name = call.args.get("profile", "default")
    allowed_tools = call.args.get("allowed_tools", [])

    if not brief:
        return _result(call.id, error="brief is required", start=start)

    try:
        task_type_enum = TaskType(task_type)
    except ValueError:
        return _result(call.id, error=f"unknown task type: {task_type}", start=start)

    profile = CapabilityProfile(
        name=profile_name,
        allowed_tools=allowed_tools or _default_tools(task_type_enum),
    )

    task = Task(type=task_type_enum, brief=brief, profile=profile)

    # Import here to avoid circular dependency at module load
    from thrall.tasks.pool import submit
    await submit(task)

    state.increment_tasks()
    return _result(call.id, output=f"task spawned: {task.id} [{task_type}]", start=start)


def _default_tools(task_type: TaskType) -> list[str]:
    if task_type == TaskType.SHELL:
        return ["code.execute"]
    return ["filesystem.read", "filesystem.glob", "filesystem.grep", "web.fetch", "web.search", "web.scrape"]


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "workers_spawn"
DESCRIPTION = "Spawn an ephemeral worker task with a capability profile."
PARAMETERS = {
    "brief": {"type": "string", "required": True},
    "type": {"type": "string", "required": False, "default": "local"},
    "profile": {"type": "string", "required": False, "default": "default"},
    "allowed_tools": {"type": "array", "items": {"type": "string"}, "required": False, "default": []},
}
