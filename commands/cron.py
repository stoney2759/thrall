from __future__ import annotations
import uuid
from datetime import datetime, timezone
from commands.base import Command, CommandContext


class CronCommand(Command):
    def name(self) -> str:
        return "cron"

    def description(self) -> str:
        return "Add a timed or recurring job: /cron <schedule> <task> [agent=<name>] [silent]"

    async def execute(self, ctx: CommandContext) -> str:
        if len(ctx.args) < 2:
            return (
                "Usage: /cron <schedule> <task> [agent=<name>] [silent]\n"
                "Example: /cron 'every monday at 9am' check the news and report"
            )

        from scheduler.job import Job
        from scheduler.parser import parse_schedule
        from scheduler import store

        raw_schedule = ctx.args[0]
        output_mode = "silent" if "silent" in ctx.args else "verbose"
        agent = next((a.split("=", 1)[1] for a in ctx.args if a.startswith("agent=")), None)
        task_parts = [a for a in ctx.args[1:] if not a.startswith("agent=") and a != "silent"]
        task = " ".join(task_parts)

        try:
            parsed = await parse_schedule(raw_schedule)
        except ValueError as e:
            return f"Could not parse schedule: {e}"

        job = Job(
            id=uuid.uuid4().hex[:8],
            type="cron",
            schedule=raw_schedule,
            cron_expr=parsed.cron_expr,
            human_summary=parsed.human_summary,
            task=task,
            agent=agent,
            output_mode=output_mode,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        store.add_job(job)

        agent_str = f" | agent: {agent}" if agent else ""
        return f"Job {job.id} scheduled\nSchedule: {parsed.human_summary}\nTask: {task[:100]}{agent_str}"
