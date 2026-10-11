"""Keep the Telegram chat and the webapp chat showing the same conversation.

The Telegram bot and the API server (webapp) run as separate processes, so in-process
calls between them never worked. This uses:
  - Telegram → webapp: POST to the API server's local-only /internal/sync endpoint,
    authenticated with a secret derived from TELEGRAM_BOT_TOKEN (both processes load it).
  - webapp → Telegram: the Telegram Bot API directly, with the same token.

Display sync only — each process still has its own session memory.
"""
from __future__ import annotations
import hashlib
import logging
import os
import httpx
from bootstrap import state
from constants.sync import (
    SYNC_PATH, SYNC_HEADER, SYNC_TIMEOUT_SECONDS, SYNC_DEFAULT_PORT, TELEGRAM_API_URL, TELEGRAM_MAX_MESSAGE,
)

logger = logging.getLogger(__name__)


def internal_token() -> str:
    """Shared secret for /internal/sync — empty when no Telegram token is configured (sync disabled)."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        return ""
    return hashlib.sha256(f"thrall-sync:{bot_token}".encode("utf-8")).hexdigest()


def primary_chat_id(config: dict) -> int | None:
    """First allowed Telegram user id, or None if missing or not a number."""
    allowed = config.get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])
    if not allowed:
        return None
    try:
        return int(allowed[0])
    except (TypeError, ValueError):
        return None


def webapp_sync_url(config: dict) -> str:
    port = int(config.get("server", {}).get("port", SYNC_DEFAULT_PORT))
    return f"http://127.0.0.1:{port}{SYNC_PATH}"


async def push_to_webapp(role: str, content: str) -> bool:
    """Telegram process → show this message in open webapp windows. Never raises."""
    token = internal_token()
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=SYNC_TIMEOUT_SECONDS) as client:
            r = await client.post(webapp_sync_url(state.get_config()),
                                  headers={SYNC_HEADER: token}, json={"role": role, "content": content})
            return r.status_code == 200
    except Exception as e:
        logger.debug("Webapp sync skipped (API server not reachable): %s", e)
        return False


async def push_to_telegram(text: str) -> bool:
    """API-server process → send this text to the primary Telegram chat. Never raises."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = primary_chat_id(state.get_config())
    if not bot_token or chat_id is None or not text:
        return False
    try:
        async with httpx.AsyncClient(timeout=SYNC_TIMEOUT_SECONDS) as client:
            for i in range(0, len(text), TELEGRAM_MAX_MESSAGE):
                r = await client.post(TELEGRAM_API_URL.format(token=bot_token),
                                      json={"chat_id": chat_id, "text": text[i:i + TELEGRAM_MAX_MESSAGE]})
                if r.status_code != 200:
                    logger.warning("Telegram sync failed: HTTP %s", r.status_code)
                    return False
        return True
    except Exception as e:
        logger.warning("Telegram sync failed: %s", type(e).__name__)
        return False
