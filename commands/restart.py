from __future__ import annotations
from commands.base import Command, CommandContext


class RestartCommand(Command):
    def name(self) -> str:
        return "restart"

    def description(self) -> str:
        return "Hot-reload config and reset runtime state without killing the process"

    async def execute(self, ctx: CommandContext) -> str:
        from bootstrap.startup import reload
        reload()
        return "Reloaded."
