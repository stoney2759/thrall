from __future__ import annotations
import asyncio
import json
import os
import uuid
from uuid import uuid4
from fastapi import WebSocket, WebSocketDisconnect
from schemas.message import Message, Role, Transport
from bootstrap import state
from thrall import coordinator
from transports.desktop import manager
from services import transport_sync, ask_user_channel, progress
from constants.sync import WEBAPP_USER_LABEL

_WS_COORDINATOR_TIMEOUT = 600  # 10 min hard cap on any single coordinator call


def _primary_telegram_session() -> uuid.UUID:
    allowed = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])
    if allowed:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram:{allowed[0]}")
    return uuid4()


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

    session_id = _primary_telegram_session()
    await _send(ws, {"type": "ready", "session_id": str(session_id)})
    manager.register(ws)

    # Each message runs as its own task so this loop keeps reading: replies to permission
    # questions get through, and messages sent mid-task are queued (coordinator interjections).
    send_lock = asyncio.Lock()
    running: set[asyncio.Task] = set()

    async def send(data: dict) -> None:
        async with send_lock:  # several tasks share one socket
            await _send(ws, data)

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
                await send({"type": "pong"})
                continue

            if frame_type != "message":
                await send({"type": "error", "message": f"unknown type: {frame_type!r}"})
                continue

            content = str(frame.get("content", "")).strip()
            if not content:
                await send({"type": "error", "message": "empty message"})
                continue

            # Use the client's tab session_id if provided, otherwise fall back to connection-level
            raw_sid = frame.get("session_id")
            try:
                msg_session_id = uuid.UUID(raw_sid) if raw_sid else session_id
            except (ValueError, AttributeError):
                msg_session_id = session_id

            # Questions to the user (permission prompts, interaction_ask_user) appear as notices
            sid_text = str(msg_session_id)

            async def ask_sender(question: str, sid_text: str = sid_text) -> None:
                await send({"type": "notice", "content": question, "session_id": sid_text})

            ask_user_channel.register_sender(msg_session_id, ask_sender)

            # A reply to a pending question goes to the waiting tool, not to Thrall as a new message
            if ask_user_channel.has_pending(msg_session_id):
                ask_user_channel.deliver_reply(msg_session_id, content)
                continue

            task = asyncio.create_task(_process(content, msg_session_id, send))
            running.add(task)
            task.add_done_callback(running.discard)

    except WebSocketDisconnect:
        pass
    finally:
        for task in running:
            task.cancel()
        manager.unregister(ws)


async def _process(content: str, session_id: uuid.UUID, send) -> None:
    """Handle one webapp message: run it, stream progress, send the reply, mirror to Telegram."""
    sid_text = str(session_id)
    if content.startswith("/"):
        await send({"type": "typing", "session_id": sid_text})
        response = await _dispatch_command(content, sid_text)
        await send({"type": "response", "content": response, "reasoning": None, "session_id": sid_text})
        return

    # Already working in this session → the coordinator queues it; just show the acknowledgement
    if state.has_active_task(sid_text):
        message = Message(session_id=session_id, role=Role.USER, content=content,
                          transport=Transport.API, user_id="desktop")
        ack = await coordinator.receive(message)
        await send({"type": "notice", "content": ack, "session_id": sid_text})
        return

    await send({"type": "typing", "session_id": sid_text})

    async def on_progress(text: str) -> None:
        await send({"type": "progress", "text": text, "session_id": sid_text})

    progress.register(session_id, on_progress)
    message = Message(session_id=session_id, role=Role.USER, content=content,
                      transport=Transport.API, user_id="desktop")
    try:
        response = await asyncio.wait_for(coordinator.receive(message), timeout=_WS_COORDINATOR_TIMEOUT)
    except asyncio.TimeoutError:
        response = "Request timed out after 10 minutes."
    finally:
        progress.unregister(session_id, on_progress)

    # Mirror the exchange to Telegram (bot runs in another process — Bot API directly)
    asyncio.create_task(transport_sync.push_to_telegram(f"{WEBAPP_USER_LABEL} {content}\n\n{response}"))
    await send({"type": "response", "content": response, "reasoning": None, "session_id": sid_text})


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
