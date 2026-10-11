from __future__ import annotations
from commands.base import Command, CommandContext
from bootstrap import state
from services import session_memory


class TokensCommand(Command):
    def name(self) -> str:
        return "tokens"

    def description(self) -> str:
        return "Show token usage, context size, and cost for the current session"

    async def execute(self, ctx: CommandContext) -> str:
        session_id = ctx.session_id

        # ── Session context ────────────────────────────────────────────────────
        sess = session_memory.get_or_create(session_id)
        ctx_msgs = session_memory.get_context(session_id)
        session_token_est = session_memory.estimate_tokens(session_id)
        msg_count = len(ctx_msgs)

        # Count message types in session
        tool_msgs  = sum(1 for m in ctx_msgs if m.get("role") == "tool")
        asst_msgs  = sum(1 for m in ctx_msgs if m.get("role") == "assistant")
        user_msgs  = sum(1 for m in ctx_msgs if m.get("role") == "user")

        # ── Static context overhead (estimated per turn) ───────────────────────
        identity_dir = state.get_identity_baselines_dir() if hasattr(state, "get_identity_baselines_dir") else None
        from pathlib import Path
        idir = Path(__file__).parent.parent / "identity"
        static_bytes = sum(
            (idir / f).stat().st_size
            for f in ("SOUL.md", "IDENTITY.md", "RULES.md")
            if (idir / f).exists()
        )
        static_est = static_bytes // 4

        # Tool definitions — count registered tools
        from thrall.tools import registry as tools
        tool_count = len(tools.list_tools())
        tool_def_est = tool_count * 80  # ~80 tokens per tool definition on average

        # ── Episode injection estimate ─────────────────────────────────────────
        from constants.memory import MAX_EPISODES, MAX_EPISODE_DISPLAY_CHARS
        display_cap = state.get_config().get("memory", {}).get("episode_display_chars", MAX_EPISODE_DISPLAY_CHARS)
        if display_cap:
            episode_est = f"up to {MAX_EPISODES * display_cap // 4:,} tokens (capped at {display_cap} chars/ep)"
        else:
            episode_est = f"up to {MAX_EPISODES * 8000 // 4:,} tokens (NO CAP — set episode_display_chars in config)"

        # ── LLM provider + model ──────────────────────────────────────────────────
        from services.llm.router import get_provider
        from services.llm.client import _model
        provider_name = get_provider().name()
        active_model = _model(None)

        # ── Execution mode ─────────────────────────────────────────────────────
        em_cfg = state.get_config().get("execution_mode", {})
        ceiling = int(em_cfg.get("token_ceiling", 400000))
        em_active = sess.execution_mode

        # ── Lifetime cost ──────────────────────────────────────────────────────
        total_cost = state.get_total_cost()
        session_cost = state.get_session_cost(str(session_id))
        model_usage = {}
        for model, usage in state._STATE.model_usage.items():
            model_usage[model] = usage

        # ── Format output ──────────────────────────────────────────────────────
        lines = [
            "**Token Usage Report**",
            "",
            "**Session Context (hot memory)**",
            f"  Messages: {msg_count} ({user_msgs} user, {asst_msgs} assistant, {tool_msgs} tool results)",
            f"  Estimated tokens: ~{session_token_est:,}",
            "",
            "**Static Overhead (per turn)**",
            f"  Identity files (SOUL + IDENTITY + RULES): ~{static_est:,} tokens",
            f"  Tool definitions ({tool_count} tools): ~{tool_def_est:,} tokens",
            f"  Episode memory injection: {episode_est}",
            "",
            "**Execution Mode**",
            f"  Active: {em_active}",
            f"  Ceiling: {ceiling:,} tokens",
        ]

        if em_active and sess.execution_mode_started_at:
            from datetime import datetime, timezone
            elapsed = (datetime.now(timezone.utc) - sess.execution_mode_started_at).total_seconds()
            lines.append(f"  Running for: {int(elapsed)}s")

        lines += [
            "",
            "**Cost**",
            f"  This session: ${session_cost:.4f}",
            f"  All time: ${total_cost:.4f}",
        ]

        if model_usage:
            lines.append("")
            lines.append("**By Model**")
            for model, u in model_usage.items():
                lines.append(
                    f"  {provider_name} — {model}: {u.input_tokens + u.output_tokens:,} tokens | ${u.cost_usd:.4f}"
                )

        return "\n".join(lines)
