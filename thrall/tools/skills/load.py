from __future__ import annotations
import time
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult
from services import skills
from constants.skills import SKILL_FILENAME, SKILL_MAX_CHARS, SKILL_RESOURCE_LIST_MAX


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    name = str(call.args.get("name", "")).strip()
    if not name:
        return _result(call.id, start, error="name is required — pick one from the Skills list in your context")

    dirs = skills.configured_dirs(state.get_config())
    ignore = skills.ignored_names(state.get_config())
    found = skills.all_skills(dirs)
    if name not in found:
        found = skills.refresh(dirs)  # a skill may have been added since the last scan
    info = None if name in ignore else found.get(name)
    if info is None:
        available = ", ".join(sorted(n for n in found if n not in ignore)) or "(none installed)"
        return _result(call.id, start, error=f"no skill named '{name}'. Available: {available}")

    try:
        body = info.path.read_text(encoding="utf-8")
    except OSError as e:
        return _result(call.id, start, error=f"could not read {info.path}: {e}")
    if len(body) > SKILL_MAX_CHARS:
        body = body[:SKILL_MAX_CHARS] + f"\n\n[skill cut at {SKILL_MAX_CHARS:,} chars — read the rest from {info.path}]"

    folder = info.path.parent
    extras = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != SKILL_FILENAME)
    lines = [f"# Skill loaded: {info.name}", f"Folder: {folder}", "", body]
    if extras:
        lines += ["", "## Files in this skill (read them with filesystem_read when the instructions refer to them)"]
        lines += [f"- {p}" for p in extras[:SKILL_RESOURCE_LIST_MAX]]
        if len(extras) > SKILL_RESOURCE_LIST_MAX:
            lines.append(f"- ... and {len(extras) - SKILL_RESOURCE_LIST_MAX} more")
    return _result(call.id, start, output="\n".join(lines))


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "skill_load"
DESCRIPTION = (
    "Load a skill's full instructions into context. Skills are packaged workflows listed in the "
    "'Skills' block of your context (name + when to use). When a request matches a skill, load it "
    "BEFORE starting the work and follow its instructions."
)
PARAMETERS = {
    "name": {"type": "string", "required": True},
}
