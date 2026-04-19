from __future__ import annotations
from commands.base import Command, CommandContext


class DelJobCommand(Command):
    def name(self) -> str:
        return "deljob"

    def description(self) -> str:
        return "Delete a scheduled job by ID"

    async def execute(self, ctx: CommandContext) -> str:
        if not ctx.args:
            return "Usage: /deljob <job-id>"
        from scheduler import store
        job_id = ctx.args[0].strip()
        deleted = store.delete_job(job_id)
        return f"Job `{job_id}` deleted." if deleted else f"No job found with id '{job_id}'."
