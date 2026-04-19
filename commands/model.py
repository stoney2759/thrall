from __future__ import annotations
from commands.base import Command, CommandContext
from bootstrap import state


_VALID_EFFORTS = {"low", "medium", "high"}


class ModelCommand(Command):
    def name(self) -> str:
        return "model"

    def description(self) -> str:
        return "Show or switch model: /model <name> [low|medium|high]"

    async def execute(self, ctx: CommandContext) -> str:
        if not ctx.args:
            current = state.get_model_override() or state.get_config().get("llm", {}).get("model", "unknown")
            effort = state.get_reasoning_effort() or state.get_config().get("llm", {}).get("reasoning_effort") or "off"
            return f"Model: {current}\nReasoning: {effort}\n\nUsage: /model <name> [low|medium|high|off]"

        model = ctx.args[0]
        state.set_model_override(model)
        reply = f"Model: {model}"

        if len(ctx.args) >= 2:
            effort = ctx.args[1].lower()
            if effort == "off":
                state.set_reasoning_effort(None)
                reply += "\nReasoning: off"
            elif effort in _VALID_EFFORTS:
                state.set_reasoning_effort(effort)
                reply += f"\nReasoning: {effort}"
            else:
                reply += f"\nUnknown reasoning value '{effort}' — use low, medium, high, or off"

        return reply
