from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from commands.base import CommandContext
from commands.stop import StopCommand
from commands.watch import WatchCommand
from schemas.message import Transport


@pytest.mark.asyncio
async def test_watch_starts_video_processor_in_background(monkeypatch):
    captured = {}

    async def fake_submit(task):
        captured["task"] = task
        return SimpleNamespace(task=task)

    monkeypatch.setattr("components.agents.utils.load_agent", lambda name: SimpleNamespace(
        soul="video processor soul",
        allowed_tools=["video_download"],
    ))
    monkeypatch.setattr("thrall.tasks.pool.list_active", lambda: [])
    monkeypatch.setattr("thrall.tasks.pool.submit", fake_submit)

    ctx = CommandContext(
        user_id="user",
        session_id=uuid4(),
        transport=Transport.TELEGRAM,
        args=["https://example.com/video"],
    )

    result = await WatchCommand().execute(ctx)

    assert "Video processing started in the background." in result
    assert captured["task"].profile.name == "video-processor"
    assert captured["task"].soul_override == "video processor soul"
    assert captured["task"].silent is False


@pytest.mark.asyncio
async def test_stop_with_task_id_cancels_background_task(monkeypatch):
    task_id = uuid4()
    cancelled = {}

    async def fake_cancel(value):
        cancelled["task_id"] = value
        return True

    monkeypatch.setattr("thrall.tasks.pool.cancel", fake_cancel)

    ctx = CommandContext(
        user_id="user",
        session_id=uuid4(),
        transport=Transport.CLI,
        args=[str(task_id)],
    )

    result = await StopCommand().execute(ctx)

    assert cancelled["task_id"] == task_id
    assert result == f"Stopping task {task_id}..."
