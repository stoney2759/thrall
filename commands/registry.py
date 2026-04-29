from __future__ import annotations
from commands.base import Command, CommandContext
from commands.status import StatusCommand
from commands.cost import CostCommand
from commands.help import HelpCommand
from commands.clear import ClearCommand
from commands.model import ModelCommand
from commands.tasks import TasksCommand
from commands.memory import MemoryCommand
from commands.health import HealthCommand
from commands.restart import RestartCommand
from commands.jobs import JobsCommand
from commands.deljob import DelJobCommand
from commands.compact import CompactCommand
from commands.compact_confirm import CompactConfirmCommand
from commands.compact_cancel import CompactCancelCommand
from commands.profile import ProfileCommand
from commands.cron import CronCommand
from commands.heartbeat import HeartbeatCommand
from commands.stop import StopCommand

_COMMANDS: dict[str, Command] = {
    cmd.name(): cmd
    for cmd in [
        StatusCommand(),
        CostCommand(),
        HelpCommand(),
        ClearCommand(),
        ModelCommand(),
        TasksCommand(),
        MemoryCommand(),
        HealthCommand(),
        RestartCommand(),
        JobsCommand(),
        DelJobCommand(),
        CompactCommand(),
        CompactConfirmCommand(),
        CompactCancelCommand(),
        ProfileCommand(),
        CronCommand(),
        HeartbeatCommand(),
        StopCommand(),
    ]
}


def all_commands() -> list[Command]:
    return list(_COMMANDS.values())


async def dispatch(name: str, ctx: CommandContext) -> str | None:
    """Returns the command response, or None if the command name is not registered."""
    cmd = _COMMANDS.get(name.lstrip("/").lower())
    if cmd is None:
        return None
    return await cmd.execute(ctx)
