from __future__ import annotations
from commands.base import Command, CommandContext
from bootstrap import state


class StopCommand(Command):
    def name(self) -> str:
        return "stop"

    def description(self) -> str:
        return "Cancel the currently running task for this session"

    async def execute(self, ctx: CommandContext) -> str:
        session_key = str(ctx.session_id)
        if not state.has_active_task(session_key):
            return "No task is running."
        cancelled = state.cancel_task(session_key)
        return "Stopping..." if cancelled else "Nothing to stop."
