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
    dead: set[WebSocket] = set()
    for ws in _connections:
        try:
            await ws.send_text(frame)
        except Exception:
            dead.add(ws)
    _connections -= dead
