from __future__ import annotations
from commands.base import Command, CommandContext
from bootstrap import state


_VALID_EFFORTS = {"low", "medium", "high"}


class ModelCommand(Command):
    def name(self) -> str:
        return "model"

    def description(self) -> str:
        return "Show or switch model/profile: /model | /model @profile | /model <name> [low|medium|high]"

    async def execute(self, ctx: CommandContext) -> str:
        from services.llm.router import list_profiles, get_model_for_profile
        from services.auth.credentials import get

        # No args — show current state
        if not ctx.args:
            llm_profile = state.get_active_llm_profile()
            model_override = state.get_model_override()
            effort = state.get_reasoning_effort() or state.get_config().get("llm", {}).get("reasoning_effort") or "off"

            if llm_profile:
                profile_def = list_profiles().get(llm_profile, {})
                provider = profile_def.get("provider", "unknown")
                model = get_model_for_profile(llm_profile) or model_override or "unknown"
                lines = [f"Profile: @{llm_profile}", f"Model: {model}", f"Provider: {provider}", f"Reasoning: {effort}"]
            else:
                provider = state.get_config().get("llm", {}).get("provider", "openrouter")
                model = model_override or state.get_config().get("llm", {}).get("model", "unknown")
                lines = [f"Profile: default", f"Model: {model}", f"Provider: {provider}", f"Reasoning: {effort}"]

            usage = state.get_model_usage()
            if model in usage:
                u = usage[model]
                lines.append(f"Usage: {u.input_tokens:,} in / {u.output_tokens:,} out / ${u.cost_usd:.4f}")

            profiles = list_profiles()
            if profiles:
                lines.append("\nAvailable profiles:")
                for name in profiles:
                    lines.append(f"  @{name}")

            lines.append("\nUsage: /model @profile | /model <name> [low|medium|high|off]")
            return "\n".join(lines)

        first = ctx.args[0]

        # Profile switch: /model @profile-name [--global]
        if first.startswith("@"):
            profile_name = first[1:]
            profiles = list_profiles()

            if profile_name not in profiles:
                available = ", ".join(f"@{p}" for p in profiles) or "none defined"
                return f"Unknown profile '@{profile_name}'. Available: {available}"

            profile = profiles[profile_name]
            provider = profile.get("provider", "")
            credential_name = profile.get("credential", "")

            # Check credential is present for non-openrouter providers
            if provider != "openrouter" and credential_name:
                cred = get(credential_name)
                if not cred:
                    return (
                        f"Profile '@{profile_name}' requires credential '{credential_name}' "
                        f"but it's not configured in auth-profiles.json."
                    )
                token_empty = (
                    (cred.get("type") == "oauth" and not cred.get("access_token"))
                    or (cred.get("type") == "api_key" and not cred.get("key"))
                )
                if token_empty:
                    return (
                        f"Profile '@{profile_name}' credential '{credential_name}' has no token. "
                        f"Run `/auth @{profile_name}` to authenticate."
                    )

            persist = "--global" in ctx.args
            state.set_active_llm_profile(profile_name)
            model = profile.get("model", "unknown")

            if persist:
                from services.runtime_preferences import save_llm
                save_llm(active_profile=profile_name)
                reply = f"Profile: @{profile_name}\nModel: {model}\nProvider: {provider}\n(saved as default — survives restart)"
            else:
                reply = f"Profile: @{profile_name}\nModel: {model}\nProvider: {provider}\n(session only — use --global to persist)"

            # Clear any manual model override when switching profiles
            state.set_model_override(None)
            return reply

        # Legacy: /model <name> [effort]
        model = first
        state.set_model_override(model)
        state.set_active_llm_profile(None)
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
