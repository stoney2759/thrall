"""Live progress — what Thrall is doing right now, shown while a task runs.

The coordinator calls `emit(session_id, label)` before each tool call. Transports register a
listener for the session (Telegram, webapp, CLI) and display the steps their own way.
`StatusBoard` is the shared "one message, edited in place" display with throttling, used by
Telegram (edit_message_text) and testable without a network.

Labels carry the tool name and at most a file name — never arguments, commands or content.
"""
from __future__ import annotations
import asyncio
import logging
import time
from pathlib import PurePath
from typing import Awaitable, Callable
from uuid import UUID
from constants.progress import (
    PROGRESS_HEADER, PROGRESS_STEP_PREFIX, PROGRESS_VISIBLE_STEPS, PROGRESS_MIN_EDIT_SECONDS,
    PROGRESS_TARGET_MAX, PROGRESS_LABELS,
)

logger = logging.getLogger(__name__)

_listeners: dict[UUID, Callable[[str], Awaitable[None]]] = {}


def register(session_id: UUID, listener: Callable[[str], Awaitable[None]]) -> None:
    _listeners[session_id] = listener


def unregister(session_id: UUID, listener: Callable[[str], Awaitable[None]] | None = None) -> None:
    """Remove the session's listener (only if it is still `listener`, when given)."""
    if listener is None or _listeners.get(session_id) is listener:
        _listeners.pop(session_id, None)


async def emit(session_id: UUID, text: str) -> None:
    listener = _listeners.get(session_id)
    if listener is None:
        return
    try:
        await listener(text)
    except Exception as e:  # progress must never break a task
        logger.debug("Progress listener failed for %s: %s", session_id, e)


def label(tool: str, args: dict) -> str:
    """'deckcraft: add slide' / 'writing ideas.txt' — tool + file name only."""
    server, sep, short = tool.partition("__")
    if sep:
        base = f"{server}: {short.replace('_', ' ')}"
    else:
        base = PROGRESS_LABELS.get(tool, tool.replace("_", " "))
    target = ""
    for key in ("path", "file_path", "output_path"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            target = PurePath(value.replace("\\", "/")).name
            break
    if not target and tool == "skill_load" and isinstance(args.get("name"), str):
        target = args["name"]
    if len(target) > PROGRESS_TARGET_MAX:
        target = target[:PROGRESS_TARGET_MAX] + "…"
    return f"{base} {target}".strip()


class StatusBoard:
    """One status message, edited in place as steps arrive, throttled to stay under rate limits.

    send(text) -> handle, edit(handle, text), delete(handle) are supplied by the transport.
    """

    def __init__(self, send: Callable[[str], Awaitable[object]], edit: Callable[[object, str], Awaitable[None]],
                 delete: Callable[[object], Awaitable[None]], min_interval: float = PROGRESS_MIN_EDIT_SECONDS) -> None:
        self._send, self._edit, self._delete = send, edit, delete
        self._min_interval = min_interval
        self._steps: list[str] = []
        self._handle: object | None = None
        self._last_push = 0.0
        self._flush_task: asyncio.Task | None = None
        self._closed = False
        self._push_lock = asyncio.Lock()  # parallel tool calls emit together — only one send/edit at a time

    def render(self) -> str:
        shown = self._steps[-PROGRESS_VISIBLE_STEPS:]
        hidden = len(self._steps) - len(shown)
        lines = [PROGRESS_HEADER + (f" ({len(self._steps)} steps)" if hidden else "")]
        lines += [f"{PROGRESS_STEP_PREFIX} {s}" for s in shown]
        return "\n".join(lines)

    async def add(self, step: str) -> None:
        if self._closed:
            return
        if self._steps and self._steps[-1] == step:
            return  # repeated identical step (e.g. many draw calls) — nothing new to show
        self._steps.append(step)
        if self._push_lock.locked():
            # a send/edit is in flight — make sure one more push follows it with the latest steps
            if self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._flush_after(self._min_interval))
            return
        wait = self._min_interval - (time.monotonic() - self._last_push)
        if self._handle is None or wait <= 0:
            await self._push()
        elif self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_after(wait))

    async def _flush_after(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if not self._closed:
            await self._push()

    async def _push(self) -> None:
        async with self._push_lock:
            if self._closed:
                return
            self._last_push = time.monotonic()
            try:
                if self._handle is None:
                    self._handle = await self._send(self.render())
                else:
                    await self._edit(self._handle, self.render())
            except Exception as e:
                logger.debug("Status board update failed: %s", e)

    async def close(self) -> None:
        """Task finished — remove the status message so only the real reply remains."""
        self._closed = True
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        async with self._push_lock:  # let an in-flight first send finish so its message gets deleted
            pass
        if self._handle is not None:
            try:
                await self._delete(self._handle)
            except Exception as e:
                logger.debug("Status board delete failed: %s", e)
