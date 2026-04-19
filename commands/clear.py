from __future__ import annotations
from commands.base import Command, CommandContext
from services.session_memory import session_memory


class ClearCommand(Command):
    def name(self) -> str:
        return "clear"

    def description(self) -> str:
        return "Clear session memory for this session"

    async def execute(self, ctx: CommandContext) -> str:
        session_memory.clear(ctx.session_id)
        return "Session memory cleared."
