from __future__ import annotations
from commands.base import Command, CommandContext


class HelpCommand(Command):
    def name(self) -> str:
        return "help"

    def description(self) -> str:
        return "List available commands"

    async def execute(self, ctx: CommandContext) -> str:
        from commands.registry import all_commands
        lines = ["Commands:"]
        for cmd in sorted(all_commands(), key=lambda c: c.name()):
            lines.append(f"  /{cmd.name():<12} {cmd.description()}")
        return "\n".join(lines)
