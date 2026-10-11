"""Mid-task user messages.

When a message arrives for a session whose reasoning loop is already running, the
coordinator queues it here instead of refusing it. The running loop drains the
queue before each LLM call and injects the messages as user turns.
"""
from __future__ import annotations
from uuid import UUID
from constants.coordinator import MAX_PENDING_INTERJECTIONS

_pending: dict[UUID, list[str]] = {}


def add(session_id: UUID, content: str) -> int:
    """Queue a message for the running task. Returns the number now pending."""
    queue = _pending.setdefault(session_id, [])
    queue.append(content)
    if len(queue) > MAX_PENDING_INTERJECTIONS:
        del queue[: len(queue) - MAX_PENDING_INTERJECTIONS]
    return len(queue)


def drain(session_id: UUID) -> list[str]:
    """Remove and return every pending message for the session, oldest first."""
    return _pending.pop(session_id, [])


def has_pending(session_id: UUID) -> bool:
    return bool(_pending.get(session_id))


def clear(session_id: UUID) -> None:
    _pending.pop(session_id, None)
