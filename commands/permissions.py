from __future__ import annotations
from commands.base import Command, CommandContext
from bootstrap import state
from services import permissions
from constants.permissions import PERMISSION_MODES, MODE_ASK, MODE_TRUSTED, MODE_READ_ONLY

_MODE_HELP = {
    MODE_ASK: "reads run freely; anything that changes something asks you first",
    MODE_TRUSTED: "everything runs without asking",
    MODE_READ_ONLY: "nothing that changes anything can run",
}


class PermissionsCommand(Command):
    def name(self) -> str:
        return "permissions"

    def description(self) -> str:
        return "Show or set the permission mode: ask, trusted, read_only (reset = back to config)"

    async def execute(self, ctx: CommandContext) -> str:
        config = state.get_config()
        if ctx.args:
            wanted = str(ctx.args[0]).strip().lower()
            if wanted == "reset":
                state.set_permission_mode_override(None)
                permissions.clear_session(ctx.session_id)
            elif wanted in PERMISSION_MODES:
                state.set_permission_mode_override(wanted)
            else:
                return f"Unknown mode '{wanted}'. Use one of: {', '.join(PERMISSION_MODES)}, or reset."
        mode = permissions.current_mode(config, state.get_permission_mode_override())
        allow, deny = permissions.config_rules(config)
        session = permissions.session_allows(ctx.session_id)
        source = "set with /permissions (until restart)" if state.get_permission_mode_override() else "from config"
        lines = [f"Permission mode: {mode} — {_MODE_HELP[mode]} ({source})"]
        lines.append(f"Allow rules: {', '.join(allow) if allow else 'none'}")
        lines.append(f"Deny rules: {', '.join(deny) if deny else 'none'}")
        lines.append(f"Allowed for this session ('always'): {', '.join(session) if session else 'none'}")
        lines.append("Change: /permissions ask | trusted | read_only | reset")
        return "\n".join(lines)
