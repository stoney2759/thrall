from __future__ import annotations
from commands.base import Command, CommandContext


class CompactConfirmCommand(Command):
    def name(self) -> str:
        return "compact_ok"

    def description(self) -> str:
        return "Confirm and apply the pending compact"

    async def execute(self, ctx: CommandContext) -> str:
        from services.compaction import compactor

        if not compactor.get_pending(ctx.session_id):
            return "No pending compact. Run /compact first."

        original_count = compactor.commit(ctx.session_id)
        return f"Memory compacted. {original_count} turns replaced with summary. session_backup.md updated."
