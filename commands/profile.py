from __future__ import annotations
from pathlib import Path
from commands.base import Command, CommandContext
from bootstrap import state
from hooks.profile_gate import scan

_IDENTITY_DIR = Path(__file__).parent.parent / "identity"


def _available_profiles() -> list[str]:
    profiles = ["default"]
    profiles_dir = _IDENTITY_DIR / "profiles"
    if profiles_dir.exists():
        profiles += [p.stem for p in sorted(profiles_dir.glob("*.md"))]
    return profiles


def _load_profile_content(name: str) -> str | None:
    if name == "default":
        path = _IDENTITY_DIR / "PERSONALITY.md"
    else:
        path = _IDENTITY_DIR / "profiles" / f"{name}.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


class ProfileCommand(Command):
    def name(self) -> str:
        return "profile"

    def description(self) -> str:
        return "Show or switch personality profile: /profile [name]"

    async def execute(self, ctx: CommandContext) -> str:
        if not ctx.args:
            current = state.get_active_profile()
            available = _available_profiles()
            return f"Active profile: {current}\nAvailable: {', '.join(available)}"

        name = ctx.args[0].lower()
        available = _available_profiles()

        if name not in available:
            return f"Profile '{name}' not found.\nAvailable: {', '.join(available)}"

        content = _load_profile_content(name)
        if content is None:
            return f"Profile '{name}' file could not be read."

        result = scan(content, name)
        if not result.allowed:
            return (
                f"Profile '{name}' rejected — security scan failed.\n"
                f"Matched: {result.matched_pattern}\n"
                f"Review the profile file and remove any instruction-override language."
            )

        state.set_active_profile(name)
        state.set_active_profile_content(content)
        return f"Profile switched to: {name}"
