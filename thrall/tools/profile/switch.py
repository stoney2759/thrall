from __future__ import annotations
import time
from pathlib import Path
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from bootstrap import state
from hooks.profile_gate import scan

_IDENTITY_DIR = Path(__file__).parent.parent.parent.parent / "identity"


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


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    name = call.args.get("name", "").strip().lower()

    if not name:
        current = state.get_active_profile()
        available = _available_profiles()
        output = f"Active profile: {current}\nAvailable: {', '.join(available)}"
        return _result(call.id, output=output, start=start)

    available = _available_profiles()
    if name not in available:
        return _result(call.id, error=f"Profile '{name}' not found. Available: {', '.join(available)}", start=start)

    content = _load_profile_content(name)
    if content is None:
        return _result(call.id, error=f"Profile '{name}' file could not be read.", start=start)

    scan_result = scan(content, name)
    if not scan_result.allowed:
        return _result(
            call.id,
            error=(
                f"Profile '{name}' rejected — security scan failed. "
                f"Matched: {scan_result.matched_pattern}. "
                f"Review the profile file and remove any instruction-override language."
            ),
            start=start,
        )

    state.set_active_profile(name)
    state.set_active_profile_content(content)
    return _result(call.id, output=f"Profile switched to: {name}", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "profile_switch"
DESCRIPTION = "Switch the active personality profile or list available profiles. Use this when the user asks to change Thrall's personality or tone."
PARAMETERS = {
    "name": {"type": "string", "required": False, "default": "", "description": "Profile name to switch to. Omit to list available profiles."},
}
