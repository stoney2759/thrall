"""
Unified launcher — starts the API server and Telegram bot in the same event loop.

Transports enabled:
  - FastAPI / WebSocket server  (always)
  - Telegram bot                (if enabled in config and TELEGRAM_BOT_TOKEN is set)

Use main.py if you only need the API server.
Use telegram_server.py if you only need Telegram.
"""
from __future__ import annotations
import asyncio
import sys
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import tomllib
from pathlib import Path
import uvicorn


def _server_cfg() -> tuple[str, int]:
    try:
        config_path = Path(__file__).parent / "config" / "config.toml"
        with open(config_path, "rb") as f:
            cfg = tomllib.load(f)
        server = cfg.get("server", {})
        return server.get("host", "0.0.0.0"), int(server.get("port", 8000))
    except Exception:
        return "0.0.0.0", 8000


async def _run_telegram(server: uvicorn.Server) -> None:
    import os
    from bootstrap import state

    tg_cfg = state.get_config().get("transports", {}).get("telegram", {})
    if not tg_cfg.get("enabled", False):
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return

    from telegram import Update
    from transports.telegram.bot import build_application, set_commands, _shutdown

    ptb_app = build_application()
    ptb_app.post_init = set_commands
    ptb_app.post_shutdown = _shutdown

    async with ptb_app:
        await ptb_app.start()
        await ptb_app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

        # Stay alive until the API server shuts down
        while not server.should_exit:
            await asyncio.sleep(0.5)

        await ptb_app.updater.stop()
        await ptb_app.stop()


async def _main() -> None:
    # Bootstrap before spawning tasks — lifespan will see _started=True and skip
    from bootstrap.startup import start
    start()

    host, port = _server_cfg()
    config = uvicorn.Config("server.app:app", host=host, port=port, loop="none")
    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),
        _run_telegram(server),
    )


if __name__ == "__main__":
    asyncio.run(_main())
