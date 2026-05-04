from __future__ import annotations
from commands.base import Command, CommandContext
from schemas.message import Message, Role


class WatchCommand(Command):
    def name(self) -> str:
        return "watch"

    def description(self) -> str:
        return "Process a video URL — download, transcribe, extract frames, describe visually, store in memory"

    async def execute(self, ctx: CommandContext) -> str:
        from thrall.coordinator import receive
        from bootstrap import state
        from services import session_memory

        url = (ctx.args or "").strip()
        if not url:
            return "Usage: /watch <video_url>\nExample: /watch https://www.youtube.com/watch?v=..."

        if not (url.startswith("http://") or url.startswith("https://")):
            return f"That doesn't look like a URL: {url!r}\nUsage: /watch <video_url>"

        session_key = str(ctx.session_id)
        if state.has_active_task(session_key):
            return "A task is already running. Send /stop to cancel it first."

        # Raise iteration cap — video processing is a long multi-step pipeline
        session_memory.set_execution_mode(ctx.session_id)

        message = Message(
            session_id=ctx.session_id,
            role=Role.USER,
            content=(
                f"Process this video using the video-processor agent: {url}\n"
                "Spawn the agent with profile=video-processor and wait for it to complete. "
                "When it finishes, relay its output to the user exactly as-is — do not summarise, reformat, or add anything. The agent's report is the final response."
            ),
            transport=ctx.transport,
            user_id=ctx.user_id,
        )
        return await receive(message)
