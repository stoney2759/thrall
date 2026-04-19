from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    description = call.args.get("description", "")
    confirm = call.args.get("confirm", False)
    name_override = call.args.get("name", "")

    if not description:
        return _result(call.id, error="description is required", start=start)

    from components.agents.utils import list_agent_names, save_agent
    from components.agents.validate import validate

    existing = list_agent_names()

    if not confirm:
        # Draft mode — generate and return for review, don't save
        try:
            from components.agents.generate import generate
            agent = await generate(description, existing)

            lines = [
                "Agent draft ready for review:",
                f"  Name        : {agent.name}",
                f"  Description : {agent.description}",
                f"  Model       : {agent.model}",
                f"  Tools       : {', '.join(agent.allowed_tools)}",
                f"\nSoul (system prompt):\n{agent.soul[:500]}{'...' if len(agent.soul) > 500 else ''}",
                "\nTo confirm creation, call agents.create again with confirm=true and the same description.",
                "To override the name, add name=<your-name>.",
            ]
            return _result(call.id, output="\n".join(lines), start=start)

        except Exception as e:
            return _result(call.id, error=f"generation failed: {e}", start=start)

    # Confirmed — generate, validate, save
    try:
        from components.agents.generate import generate
        agent = await generate(description, existing)

        if name_override:
            import re
            agent.name = re.sub(r"[^a-z0-9-]", "-", name_override.lower()).strip("-")

        errors = validate(agent, existing)
        if errors:
            return _result(call.id, error="\n".join(errors), start=start)

        path = save_agent(agent)
        return _result(
            call.id,
            output=f"Agent '{agent.name}' created and saved to catalog.\n{path.as_posix()}\n\nSpawn it with: agents.spawn brief='...' profile='{agent.name}'",
            start=start,
        )

    except Exception as e:
        return _result(call.id, error=f"creation failed: {e}", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "agents.create"
DESCRIPTION = "Create a new named agent from a description. First call shows a draft for review. Call again with confirm=true to save."
PARAMETERS = {
    "description": {"type": "string", "required": True},
    "confirm": {"type": "boolean", "required": False, "default": False},
    "name": {"type": "string", "required": False, "default": ""},
}
