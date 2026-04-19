from __future__ import annotations
from commands.base import Command, CommandContext


class CompactCancelCommand(Command):
    def name(self) -> str:
        return "compact_cancel"

    def description(self) -> str:
        return "Discard the pending compact draft"

    async def execute(self, ctx: CommandContext) -> str:
        from services.compaction import compactor

        if not compactor.get_pending(ctx.session_id):
            return "No pending compact to cancel."

        compactor.discard_pending(ctx.session_id)
        return "Compact cancelled. Session memory unchanged. Raw dump file is still preserved."
