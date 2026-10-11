from __future__ import annotations

# Telegram ↔ webapp display sync. The Telegram bot and the API server are separate processes,
# so they talk over local HTTP (webapp side) and the Telegram Bot API (Telegram side).
SYNC_PATH = "/internal/sync"
SYNC_HEADER = "X-Thrall-Sync"           # carries a secret derived from TELEGRAM_BOT_TOKEN (both processes have it)
SYNC_TIMEOUT_SECONDS = 5.0
SYNC_LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
SYNC_DEFAULT_PORT = 8000
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_MAX_MESSAGE = 4096
WEBAPP_USER_LABEL = "🖥 You (webapp):"     # how a webapp message is shown in Telegram
