from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable
from uuid import UUID

logger = logging.getLogger(__name__)

_pending: dict[UUID, asyncio.Queue] = {}
_senders: dict[UUID, Callable[[str], Awaitable[None]]] = {}


def register_sender(session_id: UUID, send_fn: Callable[[str], Awaitable[None]]) -> None:
    _senders[session_id] = send_fn


async def ask(session_id: UUID, question: str, timeout_seconds: float = 300.0) -> str:
    q: asyncio.Queue = asyncio.Queue(maxsize=1)
    _pending[session_id] = q

    send_fn = _senders.get(session_id)
    if send_fn:
        try:
            await send_fn(question)
        except Exception as e:
            logger.warning("ask_user: failed to send question to session %s: %s", session_id, e)
    else:
        logger.warning("ask_user: no sender registered for session %s", session_id)

    try:
        return await asyncio.wait_for(q.get(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return f"[Timeout: user did not reply within {int(timeout_seconds)}s]"
    finally:
        _pending.pop(session_id, None)


def has_pending(session_id: UUID) -> bool:
    return session_id in _pending


def deliver_reply(session_id: UUID, text: str) -> bool:
    q = _pending.get(session_id)
    if q is None:
        return False
    try:
        q.put_nowait(text)
        return True
    except asyncio.QueueFull:
        return False
