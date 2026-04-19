from __future__ import annotations
from commands.base import Command, CommandContext
from services.session_memory import session_memory


class MemoryCommand(Command):
    def name(self) -> str:
        return "memory"

    def description(self) -> str:
        return "Inspect session memory: /memory [list|clear|search <query>]"

    async def execute(self, ctx: CommandContext) -> str:
        sub = ctx.args[0].lower() if ctx.args else "list"

        if sub == "clear":
            session_memory.clear(ctx.session_id)
            return "Session memory cleared."

        if sub == "search":
            query = " ".join(ctx.args[1:]).lower() if len(ctx.args) > 1 else ""
            if not query:
                return "Usage: /memory search <query>"
            ctx_turns = session_memory.get_context(ctx.session_id)
            hits = [t for t in ctx_turns if query in t.get("content", "").lower()]
            if not hits:
                return f"No turns matching '{query}'."
            lines = [f"Matches for '{query}':"]
            for i, t in enumerate(hits[-10:], 1):
                snippet = t["content"][:120].replace("\n", " ")
                lines.append(f"  {i}. [{t['role']}] {snippet}")
            return "\n".join(lines)

        # default: list
        ctx_turns = session_memory.get_context(ctx.session_id)
        if not ctx_turns:
            return "Session memory is empty."
        lines = [f"Session memory ({len(ctx_turns)} turns):"]
        for i, t in enumerate(ctx_turns[-20:], 1):
            snippet = t["content"][:80].replace("\n", " ")
            lines.append(f"  {i}. [{t['role']}] {snippet}")
        return "\n".join(lines)
