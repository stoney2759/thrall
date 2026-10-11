from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable
from uuid import UUID

logger = logging.getLogger(__name__)

_pending: dict[UUID, asyncio.Queue] = {}
_senders: dict[UUID, Callable[[str], Awaitable[None]]] = {}
# Optional, per transport: show a question with tap-able choices, and update it once answered
_choice_senders: dict[UUID, Callable[[str, list[str]], Awaitable[None]]] = {}
_resolvers: dict[UUID, Callable[[str], Awaitable[None]]] = {}


def register_sender(session_id: UUID, send_fn: Callable[[str], Awaitable[None]]) -> None:
    _senders[session_id] = send_fn


def register_choice_ui(session_id: UUID, choice_fn: Callable[[str, list[str]], Awaitable[None]],
                       resolve_fn: Callable[[str], Awaitable[None]]) -> None:
    """Transports with buttons (Telegram): choice_fn shows question + choices, resolve_fn replaces
    the shown question with its outcome once answered."""
    _choice_senders[session_id] = choice_fn
    _resolvers[session_id] = resolve_fn


async def resolve(session_id: UUID, outcome: str) -> None:
    """Replace the last choice question with its outcome (no-op where the transport has no buttons)."""
    fn = _resolvers.get(session_id)
    if fn is None:
        return
    try:
        await fn(outcome)
    except Exception as e:
        logger.warning("ask_user: failed to resolve question for session %s: %s", session_id, e)


def has_sender(session_id: UUID) -> bool:
    """True if a transport can put a question in front of the user for this session."""
    return session_id in _senders


async def ask(session_id: UUID, question: str, timeout_seconds: float = 300.0,
              choices: list[str] | None = None) -> str:
    """Put a question to the user and wait for the reply. With `choices`, transports that support
    buttons show them (the reply is the chosen value); others show the plain question."""
    q: asyncio.Queue = asyncio.Queue(maxsize=1)
    _pending[session_id] = q

    choice_fn = _choice_senders.get(session_id) if choices else None
    send_fn = _senders.get(session_id)
    try:
        if choice_fn is not None:
            await choice_fn(question, list(choices))
        elif send_fn is not None:
            await send_fn(question)
        else:
            logger.warning("ask_user: no sender registered for session %s", session_id)
    except Exception as e:
        logger.warning("ask_user: failed to send question to session %s: %s", session_id, e)

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
