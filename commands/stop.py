from __future__ import annotations
from uuid import UUID
from commands.base import Command, CommandContext
from bootstrap import state


class StopCommand(Command):
    def name(self) -> str:
        return "stop"

    def description(self) -> str:
        return "Cancel the current foreground task or a background task by id"

    async def execute(self, ctx: CommandContext) -> str:
        if ctx.args:
            task_id_raw = str(ctx.args[0]).strip()
            try:
                task_id = UUID(task_id_raw)
            except ValueError:
                return f"Invalid task id: {task_id_raw}"

            from thrall.tasks import pool
            cancelled = await pool.cancel(task_id)
            return f"Stopping task {task_id}..." if cancelled else f"No active background task found for {task_id}."

        session_key = str(ctx.session_id)
        if not state.has_active_task(session_key):
            return "No task is running."
        cancelled = state.cancel_task(session_key)
        return "Stopping..." if cancelled else "Nothing to stop."
