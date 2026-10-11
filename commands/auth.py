"""Auth command — /auth @profile to authenticate a credential profile."""
from __future__ import annotations

import asyncio
import logging
import time

from commands.base import Command, CommandContext

logger = logging.getLogger(__name__)


class AuthCommand(Command):
    def name(self) -> str:
        return "auth"

    def description(self) -> str:
        return "Authenticate a credential profile: /auth @openai"

    async def execute(self, ctx: CommandContext) -> str:
        if not ctx.args or not ctx.args[0].startswith("@"):
            return (
                "Usage: /auth @profile\n\n"
                "Available profiles that support auth:\n"
                "  @openai  — OpenAI Codex (ChatGPT Pro/Plus subscription)"
            )

        profile_name = ctx.args[0][1:]

        if profile_name == "openai":
            return await _auth_openai()

        return f"No auth handler for @{profile_name}. Currently supported: @openai"


async def _auth_openai() -> str:
    from services.auth import oauth_openai

    auth_url_holder: list[str] = []

    def _capture_url(url: str) -> None:
        auth_url_holder.append(url)

    # Start the flow — this launches the callback server and calls _capture_url
    # when it's ready, then waits for the browser callback.
    flow_task = asyncio.create_task(_run_and_store(oauth_openai, _capture_url))

    # Wait a tick so the server starts and the URL is captured
    for _ in range(20):
        await asyncio.sleep(0.05)
        if auth_url_holder:
            break

    if not auth_url_holder:
        # If the task already failed we want to propagate the error
        if flow_task.done() and flow_task.exception():
            raise flow_task.exception()  # type: ignore[misc]
        return "Failed to start OAuth server — is port 1455 in use?"

    auth_url = auth_url_holder[0]
    # Don't await the task here — let it finish in the background.
    # The task will log success/failure and write the credential.
    return (
        "Open this URL in your browser to authenticate with OpenAI Codex:\n\n"
        f"{auth_url}\n\n"
        "Waiting for callback (timeout: 5 min)...\n"
        "Run /model @openai after auth completes to switch to Codex."
    )


async def _run_and_store(oauth_openai, on_url) -> None:
    """Background task: complete PKCE flow and persist the credential."""
    try:
        tokens = await oauth_openai.run_pkce_flow(on_url)

        if not tokens.get("access_token"):
            logger.error("OpenAI Codex OAuth: token exchange succeeded but access_token is empty")
            return

        from services.auth import credentials
        credentials.write_oauth(
            profile_name="openai",
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", ""),
            expires_at=tokens.get("expires_at", int(time.time()) + 3600),
            account_id=tokens.get("account_id", ""),
        )
        logger.info(
            "OpenAI Codex OAuth complete — token saved (account_id=%s)",
            tokens.get("account_id", "unknown"),
        )
    except TimeoutError:
        logger.warning("OpenAI Codex OAuth timed out — no credential saved")
    except Exception as exc:
        logger.error("OpenAI Codex OAuth failed: %s", exc, exc_info=True)
