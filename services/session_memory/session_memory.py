from __future__ import annotations
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
