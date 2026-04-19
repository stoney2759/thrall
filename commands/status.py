from __future__ import annotations
from datetime import datetime, timezone
from commands.base import Command, CommandContext
from bootstrap import state


class StatusCommand(Command):
    def name(self) -> str:
        return "status"

    def description(self) -> str:
        return "Active tasks, uptime, cost, model"

    async def execute(self, ctx: CommandContext) -> str:
        cfg = state.get_config()
        now = datetime.now(timezone.utc)
        started = cfg.get("thrall", {}).get("started_at")
        if started:
            uptime = now - datetime.fromisoformat(started)
            h, rem = divmod(int(uptime.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            uptime_str = f"{h}h {m}m {s}s"
        else:
            uptime_str = "unknown"

        provider = cfg.get("llm", {}).get("provider", "unknown")
        model = state.get_model_override() or cfg.get("llm", {}).get("model", "unknown")
        last = state.get_last_interaction().strftime("%H:%M:%S UTC")

        return "\n".join([
            "Thrall Status",
            f"  Uptime       : {uptime_str}",
            f"  Active tasks : {state.get_active_task_count()}",
            f"  Total cost   : ${state.get_total_cost():.4f}",
            f"  Provider     : {provider}",
            f"  Model        : {model}",
            f"  Workspace    : {state.get_workspace_dir() or '(not set)'}",
            f"  Last active  : {last}",
            f"  Session      : {ctx.session_id}",
        ])
