from __future__ import annotations
import asyncio
from uuid import UUID
from bootstrap import state
from services.browser.session import BrowserSession

_sessions: dict[UUID, BrowserSession] = {}
_cleanup_task: asyncio.Task | None = None


def _get_config() -> dict:
    return state.get_config().get("browser", {})


async def get_or_create(session_id: UUID) -> BrowserSession:
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(_idle_reaper())

    if session_id in _sessions and _sessions[session_id].alive:
        _sessions[session_id].touch()
        return _sessions[session_id]

    cfg = _get_config()
    session = BrowserSession(
        channel=cfg.get("channel", "chromium"),
        headless=cfg.get("headless", True),
        user_data_dir=cfg.get("user_data_dir", ""),
    )
    await session.start()
    _sessions[session_id] = session
    return session


async def close(session_id: UUID) -> None:
    if session_id in _sessions:
        await _sessions.pop(session_id).close()


async def close_all() -> None:
    for s in list(_sessions.values()):
        await s.close()
    _sessions.clear()


async def _idle_reaper() -> None:
    while True:
        await asyncio.sleep(60)
        cfg = _get_config()
        timeout = cfg.get("idle_timeout_minutes", 15) * 60
        stale = [sid for sid, s in _sessions.items() if s.idle_seconds() > timeout]
        for sid in stale:
            await close(sid)
