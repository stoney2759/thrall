from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from transports.telegram import bot as telegram_bot


class _FakeFile:
    async def download_as_bytearray(self):
        return bytearray(b"fake-bytes")


class _FakeBot:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []

    async def send_chat_action(self, chat_id, action):
        return None

    async def get_file(self, file_id):
        return _FakeFile()

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


@pytest.mark.asyncio
async def test_process_media_group_sends_one_combined_message(monkeypatch, tmp_path):
    received = {}
    fake_bot = _FakeBot()

    async def fake_describe(image_bytes, media_type="image/jpeg", prompt=""):
        return f"description for {media_type}"

    async def fake_receive(message):
        received["content"] = message.content
        return "combined response"

    monkeypatch.setattr("services.vision.openai.describe", fake_describe)
    monkeypatch.setattr(telegram_bot, "receive", fake_receive)
    monkeypatch.setattr(telegram_bot, "_uploads_dir", lambda: Path(tmp_path))

    group = telegram_bot._MediaGroup(
        chat_id=123,
        user_id="user",
        session_id=uuid4(),
        bot=fake_bot,
        items=[
            telegram_bot._MediaGroupItem(
                update_id=2,
                kind="document",
                file_id="doc-file",
                media_type="application/pdf",
                filename="brief.pdf",
                caption="file note",
            ),
            telegram_bot._MediaGroupItem(
                update_id=1,
                kind="image",
                file_id="image-file",
                media_type="image/jpeg",
                filename="image.jpg",
                caption="image note",
            ),
        ],
    )

    await telegram_bot._process_media_group(group)

    assert "[Telegram media group: 2 item(s)]" in received["content"]
    assert received["content"].find("[Image 1]") < received["content"].find("[Uploaded file 2: brief.pdf]")
    assert "description for image/jpeg" in received["content"]
    assert "User note: image note" in received["content"]
    assert "User note: file note" in received["content"]
    assert (tmp_path / "brief.pdf").exists()
    assert fake_bot.messages == [(123, "combined response")]
