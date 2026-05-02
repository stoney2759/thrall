from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from schemas.memory import SessionMemory
from schemas.message import Role


_sessions: dict[UUID, SessionMemory] = {}


def get_or_create(session_id: UUID) -> SessionMemory:
    if session_id not in _sessions:
        _sessions[session_id] = SessionMemory(session_id=session_id)
    return _sessions[session_id]


def append(session_id: UUID, role: Role, content: str) -> None:
    session = get_or_create(session_id)
    session.context.append({"role": role.value, "content": content})


def get_context(session_id: UUID) -> list[dict]:
    return get_or_create(session_id).context


def clear(session_id: UUID) -> None:
    if session_id in _sessions:
        del _sessions[session_id]


def all_sessions() -> list[UUID]:
    return list(_sessions.keys())


def estimate_tokens(session_id: UUID) -> int:
    """Rough token estimate for the session context (4 chars ≈ 1 token)."""
    context = get_or_create(session_id).context
    return sum(len(str(msg.get("content", ""))) for msg in context) // 4


def set_execution_mode(session_id: UUID) -> None:
    session = get_or_create(session_id)
    session.execution_mode = True
    session.execution_mode_started_at = datetime.now(timezone.utc)


def clear_execution_mode(session_id: UUID) -> None:
    session = get_or_create(session_id)
    session.execution_mode = False
    session.execution_mode_started_at = None
