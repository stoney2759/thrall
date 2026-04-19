from __future__ import annotations
from commands.base import Command, CommandContext


class TasksCommand(Command):
    def name(self) -> str:
        return "tasks"

    def description(self) -> str:
        return "List active tasks"

    async def execute(self, ctx: CommandContext) -> str:
        from thrall.tasks import pool
        active = pool.list_active()
        if not active:
            return "No active tasks."
        lines = [f"Active Tasks ({len(active)})"]
        for task in active:
            brief = (task.brief[:60] + "...") if len(task.brief) > 60 else task.brief
            lines.append(f"  [{task.id}] {task.type.value} / {task.status.value}\n  {brief}")
        return "\n".join(lines)
