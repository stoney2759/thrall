"""Telegram ↔ webapp display sync across the two processes."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from bootstrap import state
from services import transport_sync
from constants.sync import SYNC_PATH, SYNC_HEADER


@pytest.fixture
def bot_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    yield "123:abc"


@pytest.fixture
def synced(monkeypatch):
    """Capture what the endpoint would broadcast to webapp windows."""
    sent: list[tuple[str, str]] = []

    async def fake_sync(role, content):
        sent.append((role, content))

    monkeypatch.setattr("transports.desktop.manager.sync_message", fake_sync)
    return sent


def _client(host: str) -> TestClient:
    from server.app import app
    return TestClient(app, client=(host, 50000))  # no `with` → lifespan (startup, MCP) not run


class TestToken:
    def test_no_bot_token_means_sync_disabled(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        assert transport_sync.internal_token() == ""

    def test_token_is_derived_not_the_bot_token(self, bot_token):
        token = transport_sync.internal_token()
        assert token and bot_token not in token


class TestEndpoint:
    def test_local_caller_with_secret_is_broadcast(self, bot_token, synced):
        r = _client("127.0.0.1").post(SYNC_PATH, headers={SYNC_HEADER: transport_sync.internal_token()},
                                      json={"role": "user", "content": "hi"})
        assert r.status_code == 200 and synced == [("user", "hi")]

    def test_wrong_secret_remote_host_or_bad_role_rejected(self, bot_token, synced):
        good = {SYNC_HEADER: transport_sync.internal_token()}
        assert _client("127.0.0.1").post(SYNC_PATH, headers={SYNC_HEADER: "nope"},
                                         json={"role": "user", "content": "x"}).status_code == 403
        assert _client("203.0.113.9").post(SYNC_PATH, headers=good,
                                          json={"role": "user", "content": "x"}).status_code == 403
        assert _client("127.0.0.1").post(SYNC_PATH, headers=good,
                                         json={"role": "system", "content": "x"}).status_code == 400
        assert synced == []


class TestPushToTelegram:
    @pytest.mark.asyncio
    async def test_skips_without_chat_or_token(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        assert await transport_sync.push_to_telegram("hello") is False

    @pytest.mark.asyncio
    async def test_splits_long_text(self, monkeypatch, bot_token):
        state.set_config({"transports": {"telegram": {"allowed_user_ids": [42]}}})
        posts: list[dict] = []

        class FakeResponse:
            status_code = 200

        class FakeClient:
            def __init__(self, *a, **k): ...
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, url, json=None, headers=None):
                posts.append(json)
                return FakeResponse()

        monkeypatch.setattr(transport_sync.httpx, "AsyncClient", FakeClient)
        assert await transport_sync.push_to_telegram("x" * 5000) is True
        assert [len(p["text"]) for p in posts] == [4096, 904] and posts[0]["chat_id"] == 42
