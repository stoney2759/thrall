from __future__ import annotations
from commands.base import Command, CommandContext
from services import session_memory


class CompactCommand(Command):
    def name(self) -> str:
        return "compact"

    def description(self) -> str:
        return "Compact session memory — dump raw, summarise, validate, await approval"

    async def execute(self, ctx: CommandContext) -> str:
        from services.compaction import compactor

        context = session_memory.get_context(ctx.session_id)
        if len(context) < 4:
            return "Session too short to compact — nothing to do."

        # 1. Raw dump (unconditional, always first)
        raw_path = await compactor.raw_dump(ctx.session_id)

        # 2. Summarise
        try:
            draft = await compactor.summarise(ctx.session_id)
        except Exception as e:
            return f"Compaction failed during summarise step: {e}\nRaw dump preserved at: {raw_path.name}"

        # 3. Validate
        try:
            cleaned, flagged = await compactor.validate(draft)
        except Exception as e:
            return f"Compaction failed during validation step: {e}\nRaw dump preserved at: {raw_path.name}"

        # 4. Store pending and show draft to user
        compactor.store_pending(ctx.session_id, cleaned)

        flagged_note = ""
        if flagged:
            flagged_note = f"\n\n⚠️ Validator stripped {len(flagged)} flagged line(s) from the draft."

        turns = len(context)
        return (
            f"Raw dump saved: `{raw_path.name}`\n"
            f"Turns in session: {turns}{flagged_note}\n\n"
            f"*Proposed compact memory:*\n\n{cleaned}\n\n"
            f"Reply `/compact_ok` to apply or `/compact_cancel` to discard."
        )
