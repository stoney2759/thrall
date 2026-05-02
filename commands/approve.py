from __future__ import annotations
from commands.base import Command, CommandContext
from schemas.message import Message, Role


class ApproveCommand(Command):
    def name(self) -> str:
        return "approve"

    def description(self) -> str:
        return "Approve a pending proposal and execute the plan"

    async def execute(self, ctx: CommandContext) -> str:
        from thrall.coordinator import receive
        from bootstrap import state
        from services import session_memory

        session_key = str(ctx.session_id)
        if state.has_active_task(session_key):
            return "A task is already running. Send /stop first."

        # Raise the iteration cap and enable token/timeout guards for this session
        # so the approved plan can run past the default 30-iteration limit.
        session_memory.set_execution_mode(ctx.session_id)

        # Inject the literal `/approve` token as the synthetic user message.
        # The RULES.md → Proposal Approval rule rejects soft language like
        # "Approved" or "Proceed", so the model must see the exact trigger
        # token to satisfy its own rule.
        message = Message(
            session_id=ctx.session_id,
            role=Role.USER,
            content="/approve",
            transport=ctx.transport,
            user_id=ctx.user_id,
        )
        return await receive(message)
