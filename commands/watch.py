from __future__ import annotations
from commands.base import Command, CommandContext
from schemas.task import CapabilityProfile, Task, TaskType


class WatchCommand(Command):
    def name(self) -> str:
        return "watch"

    def description(self) -> str:
        return "Start background video processing for a URL"

    async def execute(self, ctx: CommandContext) -> str:
        url = _args_text(ctx.args).strip()
        if not url:
            return "Usage: /watch <video_url>\nExample: /watch https://www.youtube.com/watch?v=..."

        if not (url.startswith("http://") or url.startswith("https://")):
            return f"That doesn't look like a URL: {url!r}\nUsage: /watch <video_url>"

        from components.agents.utils import load_agent
        from thrall.tasks import pool
        from schemas.task import TaskStatus

        profile_name = "video-processor"
        active = [
            task for task in pool.list_active()
            if task.profile.name == profile_name and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        ]
        if active:
            return (
                f"`{profile_name}` is already running as task {active[0].id}.\n"
                "Use `/tasks` to check progress or `/stop <task_id>` to cancel it."
            )

        agent = load_agent(profile_name)
        if agent is None:
            return "The `video-processor` built-in agent is not available."

        task = Task(
            type=TaskType.LOCAL,
            brief=f"Process this video URL fully and return the final report exactly as requested by your profile: {url}",
            profile=CapabilityProfile(name=profile_name, allowed_tools=agent.allowed_tools),
            soul_override=agent.soul,
            silent=False,
            session_id=ctx.session_id,
        )
        await pool.submit(task)

        return (
            f"Video processing started in the background.\n"
            f"Task: {task.id}\n"
            "Thrall is free for new instructions while it runs. Use `/tasks` to check progress "
            f"or `/stop {task.id}` to cancel it."
        )


def _args_text(args: object) -> str:
    if isinstance(args, str):
        return args
    if isinstance(args, list):
        return " ".join(str(arg) for arg in args)
    return ""
