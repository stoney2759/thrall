from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from schemas.task import Task, TaskType, CapabilityProfile

_DEFAULT_TOOLS = [
    "filesystem.read", "filesystem.glob", "filesystem.grep",
    "filesystem.write", "filesystem.append",
    "web.fetch", "web.search", "web.scrape",
    "code.execute",
]


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    brief = call.args.get("brief", "")
    profile_name = call.args.get("profile", "default")
    allowed_tools = call.args.get("allowed_tools", [])

    if not brief:
        return _result(call.id, error="brief is required", start=start)

    # Check if profile matches a named agent in the catalog
    soul_override: str | None = None
    if profile_name and profile_name != "default":
        from components.agents.utils import load_agent
        catalog_agent = load_agent(profile_name)
        if catalog_agent:
            soul_override = catalog_agent.soul
            allowed_tools = allowed_tools or catalog_agent.allowed_tools

        # Inject prior conversation if this is a continuation
        from thrall.tasks.continuation_store import pop
        prior = pop(profile_name)
        if prior:
            brief = (
                f"[Conversation so far]\n"
                f"User: {prior['brief']}\n"
                f"You: {prior['result']}\n\n"
                f"[User replied]: {brief}"
            )

    profile = CapabilityProfile(
        name=profile_name,
        allowed_tools=allowed_tools or _DEFAULT_TOOLS,
    )

    task = Task(
        type=TaskType.LOCAL,
        brief=brief,
        profile=profile,
        soul_override=soul_override,
    )

    from thrall.tasks.pool import submit
    await submit(task)

    source = f" (loaded from catalog: {profile_name})" if soul_override else ""
    return _result(call.id, output=f"agent spawned: {task.id}{source}\nBrief: {brief[:80]}", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "agents.spawn"
DESCRIPTION = "Spawn an autonomous agent to work on a task in parallel. Use profile=<agent-name> to spawn a named agent from the catalog. Returns task_id — use agents.result to collect output."
PARAMETERS = {
    "brief": {"type": "string", "required": True},
    "profile": {"type": "string", "required": False, "default": "default"},
    "allowed_tools": {"type": "array", "required": False, "default": []},
}
