from __future__ import annotations
import json
import logging
from uuid import UUID
from hooks import audit

logger = logging.getLogger(__name__)

_SHELL_TOOLS = {"shell.run"}
_HIGH_PRIVILEGE_TOOLS = {"shell.run", "code.execute", "filesystem.write", "filesystem.edit", "filesystem.append"}

_MAX_ARG_LEN = 200


def _summarise_args(name: str, args: dict) -> str:
    if name in _SHELL_TOOLS:
        return args.get("command", "")
    try:
        s = json.dumps(args, ensure_ascii=False)
        return s if len(s) <= _MAX_ARG_LEN else s[:_MAX_ARG_LEN] + "…"
    except Exception:
        return str(args)[:_MAX_ARG_LEN]


def before_call(name: str, args: dict, caller: str, session_id: UUID) -> None:
    summary = _summarise_args(name, args)
    level = "SHELL" if name in _SHELL_TOOLS else "TOOL"
    audit.log_allow(
        f"{level}:{name}",
        reason=f"caller={caller} session={session_id} args={summary}",
    )
    if name in _HIGH_PRIVILEGE_TOOLS:
        logger.info(f"[tool] {name} | caller={caller} | {summary}")


def after_call(name: str, duration_ms: int, error: str | None) -> None:
    if error:
        audit.log_deny(
            f"TOOL:{name}",
            reason=f"error={error[:200]} duration_ms={duration_ms}",
        )
