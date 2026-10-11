"""Desktop WebSocket fan-out — sync/broadcast frames reach every open webapp tab."""
from __future__ import annotations
import json
import pytest
from transports.desktop import manager


class FakeSocket:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.frames: list[dict] = []

    async def send_text(self, text):
        if self.fail:
            raise RuntimeError("socket closed")
        self.frames.append(json.loads(text))


@pytest.fixture(autouse=True)
def clean_connections():
    manager._connections.clear()
    yield
    manager._connections.clear()


class TestSendAll:
    @pytest.mark.asyncio
    async def test_sync_reaches_open_tabs_and_drops_dead_ones(self):
        """Live bug 2026-10-11: a Telegram message crashed /internal/sync with UnboundLocalError."""
        alive, dead = FakeSocket(), FakeSocket(fail=True)
        manager.register(alive)
        manager.register(dead)
        await manager.sync_message("user", "Hey")
        assert alive.frames == [{"type": "sync", "role": "user", "content": "Hey"}]
        assert manager._connections == {alive}

    @pytest.mark.asyncio
    async def test_no_tabs_open_is_fine(self):
        await manager.broadcast("nobody listening")
