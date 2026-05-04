from __future__ import annotations
import json
import os
from uuid import uuid4
from fastapi import WebSocket, WebSocketDisconnect
from schemas.message import Message, Role, Transport
from thrall import coordinator
from transports.desktop import manager


async def handle(ws: WebSocket) -> None:
    await ws.accept()

    token_required = os.environ.get("THRALL_DESKTOP_TOKEN", "").strip()

    # Auth handshake — first frame must be {"type": "auth", "token": "..."}
    try:
        raw = await ws.receive_text()
        handshake = json.loads(raw)
    except Exception:
        await ws.close(code=1003)
        return

    if handshake.get("type") != "auth":
        await _send(ws, {"type": "error", "message": "expected auth handshake"})
        await ws.close(code=1008)
        return

    if token_required and handshake.get("token", "") != token_required:
        await _send(ws, {"type": "error", "message": "unauthorized"})
        await ws.close(code=1008)
        return

    session_id = uuid4()
    await _send(ws, {"type": "ready", "session_id": str(session_id)})
    manager.register(ws)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, {"type": "error", "message": "invalid JSON"})
                continue

            frame_type = frame.get("type")

            if frame_type == "ping":
                await _send(ws, {"type": "pong"})
                continue

            if frame_type != "message":
                await _send(ws, {"type": "error", "message": f"unknown type: {frame_type!r}"})
                continue

            content = str(frame.get("content", "")).strip()
            if not content:
                await _send(ws, {"type": "error", "message": "empty message"})
                continue

            await _send(ws, {"type": "typing"})

            if content.startswith("/"):
                response = await _dispatch_command(content, str(session_id))
            else:
                message = Message(
                    session_id=session_id,
                    role=Role.USER,
                    content=content,
                    transport=Transport.API,
                    user_id="desktop",
                )
                response = await coordinator.receive(message)

            await _send(ws, {"type": "response", "content": response, "reasoning": None})

    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister(ws)


async def _dispatch_command(content: str, session_id: str) -> str:
    from commands.base import CommandContext
    from commands.registry import dispatch

    parts = content.lstrip("/").split()
    name = parts[0].lower() if parts else ""
    args = parts[1:] if len(parts) > 1 else []

    ctx = CommandContext(
        user_id="desktop",
        session_id=session_id,
        transport=Transport.API,
        args=args,
    )

    result = await dispatch(name, ctx)
    if result is None:
        return f"Unknown command: `/{name}`. Type `/help` for available commands."
    return result


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data, ensure_ascii=False))
