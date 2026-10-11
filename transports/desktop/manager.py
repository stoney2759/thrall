from __future__ import annotations
import json
from fastapi import WebSocket

_connections: set[WebSocket] = set()


def register(ws: WebSocket) -> None:
    _connections.add(ws)


def unregister(ws: WebSocket) -> None:
    _connections.discard(ws)


async def broadcast(content: str) -> None:
    frame = json.dumps({"type": "response", "content": content}, ensure_ascii=False)
    await _send_all(frame)


async def sync_message(role: str, content: str) -> None:
    frame = json.dumps({"type": "sync", "role": role, "content": content}, ensure_ascii=False)
    await _send_all(frame)


async def _send_all(frame: str) -> None:
    dead: set[WebSocket] = set()
    for ws in list(_connections):  # copy — a socket can connect/drop while we await a send
        try:
            await ws.send_text(frame)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)
