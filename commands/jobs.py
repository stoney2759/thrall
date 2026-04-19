from __future__ import annotations
from commands.base import Command, CommandContext


class JobsCommand(Command):
    def name(self) -> str:
        return "jobs"

    def description(self) -> str:
        return "List all scheduled heartbeat and cron jobs"

    async def execute(self, ctx: CommandContext) -> str:
        from scheduler import store
        jobs = store.load_jobs()
        if not jobs:
            return "No scheduled jobs. Use /heartbeat or /cron to add one."

        lines = [f"Scheduled Jobs ({len(jobs)})"]
        for j in jobs:
            agent = f" | agent: {j.agent}" if j.agent else ""
            last = j.last_run[:19] if j.last_run else "never"
            lines.append(f"\n[{j.id}] {j.type.upper()} {j.schedule_summary()}{agent}")
            lines.append(f"  Task: {j.task[:100]}")
            lines.append(f"  Output: {j.output_mode} | Last run: {last}")
            lines.append(f"  Delete: /deljob {j.id}")

        return "\n".join(lines)
