from __future__ import annotations
import gzip
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from schemas.tool import AuditEntry, GateDecision, ToolCall
from bootstrap import state
from uuid import UUID

_AUDIT_LOG = Path(__file__).parent.parent / "state" / "audit.jsonl"
_ROTATE_LOCK = threading.Lock()


def _ensure_log() -> None:
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not _AUDIT_LOG.exists():
        _AUDIT_LOG.touch()


def _maybe_rotate() -> None:
    if not _AUDIT_LOG.exists() or _AUDIT_LOG.stat().st_size == 0:
        return
    try:
        cfg = state.get_config().get("security", {})
        max_bytes = cfg.get("audit_max_size_mb", 50) * 1024 * 1024
        retention_days = cfg.get("audit_retention_days", 7)
    except Exception:
        max_bytes = 50 * 1024 * 1024
        retention_days = 7
    if _AUDIT_LOG.stat().st_size < max_bytes:
        return
    with _ROTATE_LOCK:
        if _AUDIT_LOG.stat().st_size < max_bytes:
            return
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        rotated = _AUDIT_LOG.parent / f"audit.{timestamp}.jsonl.gz"
        with open(_AUDIT_LOG, "rb") as f_in, gzip.open(rotated, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        _AUDIT_LOG.write_text("", encoding="utf-8")
        _cleanup_old_rotations(retention_days)


def _cleanup_old_rotations(retention_days: int) -> None:
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    for f in _AUDIT_LOG.parent.glob("audit.*.jsonl.gz"):
        try:
            if datetime.utcfromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
        except Exception:
            pass


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
    _maybe_rotate()
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
