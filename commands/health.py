from __future__ import annotations
from datetime import datetime, timezone
from commands.base import Command, CommandContext
from bootstrap import state


class HealthCommand(Command):
    def name(self) -> str:
        return "health"

    def description(self) -> str:
        return "Check system health and last activity"

    async def execute(self, ctx: CommandContext) -> str:
        now = datetime.now(timezone.utc)
        last = state.get_last_interaction()
        delta = now - last
        seconds = int(delta.total_seconds())

        if seconds < 60:
            idle = f"{seconds}s ago"
        elif seconds < 3600:
            idle = f"{seconds // 60}m ago"
        else:
            idle = f"{seconds // 3600}h ago"

        errors = state.get_error_log()
        recent_errors = errors[-3:] if errors else []

        lines = [
            "Health",
            f"  Status       : alive",
            f"  Last active  : {idle}",
            f"  Active tasks : {state.get_active_task_count()}",
            f"  Total cost   : ${state.get_total_cost():.4f}",
            f"  Error count  : {len(errors)}",
        ]
        if recent_errors:
            lines.append("  Recent errors:")
            for e in recent_errors:
                ts = e.get("timestamp", "?")[:19]
                msg = e.get("error", "")[:80]
                lines.append(f"    [{ts}] {msg}")

        return "\n".join(lines)
