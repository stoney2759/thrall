from __future__ import annotations
import json
from pathlib import Path
from schemas.tool import AuditEntry, GateDecision, ToolCall
from bootstrap import state
from uuid import UUID

_AUDIT_LOG = Path(__file__).parent.parent / "state" / "audit.jsonl"


def _ensure_log() -> None:
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not _AUDIT_LOG.exists():
        _AUDIT_LOG.touch()


def log(
    gate: str,
    decision: GateDecision,
    tool_call: ToolCall | None = None,
    reason: str | None = None,
) -> AuditEntry:
    _ensure_log()
    entry = AuditEntry(
        session_id=state.get_session_id(),
        gate=gate,
        decision=decision,
        tool_call=tool_call,
        reason=reason,
    )
    with open(_AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
    return entry


def log_allow(gate: str, tool_call: ToolCall | None = None, reason: str | None = None) -> AuditEntry:
    return log(gate, GateDecision.ALLOW, tool_call, reason)


def log_deny(gate: str, tool_call: ToolCall | None = None, reason: str | None = None) -> AuditEntry:
    return log(gate, GateDecision.DENY, tool_call, reason)


def read_log(limit: int = 100) -> list[AuditEntry]:
    _ensure_log()
    lines = _AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines()
    return [AuditEntry.model_validate_json(line) for line in lines[-limit:]]
