from __future__ import annotations
from commands.base import Command, CommandContext
from bootstrap import state


class CostCommand(Command):
    def name(self) -> str:
        return "cost"

    def description(self) -> str:
        return "Token usage and spend per model"

    async def execute(self, ctx: CommandContext) -> str:
        usage = state.get_model_usage()
        lines = [f"Token Usage  —  total ${state.get_total_cost():.4f}"]
        if not usage:
            lines.append("  No usage recorded yet.")
        else:
            for model, u in usage.items():
                lines.append(
                    f"  {model}\n"
                    f"    In: {u.input_tokens:,}  Out: {u.output_tokens:,}  Cost: ${u.cost_usd:.4f}"
                )
        return "\n".join(lines)
