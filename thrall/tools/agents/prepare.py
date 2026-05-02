from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    name = call.args.get("name", "").strip()

    if not name:
        return _result(call.id, error="name is required", start=start)

    from components.agents.utils import load_agent, save_agent, find_incomplete_agents
    from components.agents.infer_tools import infer_tools

    agent = load_agent(name)
    if not agent:
        return _result(call.id, error=f"agent '{name}' not found in catalog", start=start)

    if agent.allowed_tools:
        return _result(
            call.id,
            output=f"Agent '{name}' already has tools assigned: {', '.join(agent.allowed_tools)}. No changes made.",
            start=start,
        )

    try:
        tools = await infer_tools(agent.soul)
        if not tools:
            return _result(call.id, error=f"tool inference returned no tools for '{name}'", start=start)

        agent.allowed_tools = tools
        save_agent(agent)

        return _result(
            call.id,
            output=(
                f"Agent '{name}' is ready.\n"
                f"Tools assigned: {', '.join(tools)}\n"
                f"Spawn with: agents.spawn profile='{name}' brief='<task>'"
            ),
            start=start,
        )
    except Exception as e:
        return _result(call.id, error=f"failed to prepare '{name}': {e}", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "agents_prepare"
DESCRIPTION = "Assign tools to a catalog agent that has none. Reads the agent's soul, infers appropriate tools, and saves the updated definition. Use this when the user drops a new agent into the catalog."
PARAMETERS = {
    "name": {"type": "string", "required": True},
}
