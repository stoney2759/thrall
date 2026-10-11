"""OpenAI Codex OAuth PKCE flow.

Based on the official openai/codex CLI implementation (codex-rs/login/).
Client ID and endpoints sourced from codex-rs/login/src/auth/manager.rs and server.rs.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import secrets
import time
import urllib.parse
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
_AUTH_URL = "https://auth.openai.com/oauth/authorize"
_TOKEN_URL = "https://auth.openai.com/oauth/token"
_REDIRECT_URI = "http://localhost:1455/auth/callback"
_SCOPES = "openid profile email offline_access api.connectors.read api.connectors.invoke"
_CALLBACK_PORT = 1455
_CALLBACK_TIMEOUT = 300  # 5 minutes to complete browser auth

# Module-level server state — only one PKCE flow can run at a time.
_active_server: asyncio.Server | None = None
_active_future: asyncio.Future | None = None
_active_state: str | None = None


def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge) — S256 method per RFC 7636."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _new_state() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _extract_account_id(id_token: str) -> str:
    """Pull account_id from JWT claims without verifying signature."""
    try:
        payload = id_token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        return claims.get("account_id") or claims.get("sub", "")
    except Exception:
        return ""


def build_auth_url(challenge: str, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": _CLIENT_ID,
        "redirect_uri": _REDIRECT_URI,
        "scope": _SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def _close_active_server() -> None:
    global _active_server, _active_future, _active_state
    if _active_server is not None:
        _active_server.close()
        try:
            await asyncio.wait_for(_active_server.wait_closed(), timeout=3.0)
        except asyncio.TimeoutError:
            pass
        _active_server = None
    if _active_future is not None and not _active_future.done():
        _active_future.cancel()
    _active_future = None
    _active_state = None


def _make_handler(
    expected_state: str, code_future: "asyncio.Future[str]"
) -> Callable:
    async def _handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            raw = await asyncio.wait_for(reader.read(8192), timeout=10.0)
            line = raw.decode("utf-8", errors="ignore").split("\r\n")[0]
            # "GET /auth/callback?code=...&state=... HTTP/1.1"
            parts = line.split(" ")
            path = parts[1] if len(parts) > 1 else ""
            qs = urllib.parse.urlparse(path).query
            params = dict(urllib.parse.parse_qsl(qs))

            if params.get("state") != expected_state:
                writer.write(
                    b"HTTP/1.1 400 Bad Request\r\n"
                    b"Content-Type: text/html\r\n\r\n"
                    b"<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
                    b"<h2>Session expired</h2>"
                    b"<p>Please run <code>/auth @openai</code> again and use the new URL.</p>"
                    b"</body></html>"
                )
                await writer.drain()
                writer.close()
                return

            code = params.get("code", "")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                b"<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
                b"<h2>Authentication successful!</h2>"
                b"<p>You can close this tab.</p>"
                b"</body></html>"
            )
            await writer.drain()
            writer.close()
            if code and not code_future.done():
                code_future.set_result(code)
        except Exception as exc:
            logger.error("OAuth callback handler error: %s", exc)
            if not code_future.done():
                code_future.set_exception(exc)

    return _handle


async def _exchange_code(code: str, verifier: str) -> dict:
    """Step 1: authorization_code -> id_token + refresh_token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": _CLIENT_ID,
                "code": code,
                "redirect_uri": _REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _obtain_api_key(id_token: str) -> str:
    """Step 2: id_token -> API-key style access token for actual API calls."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": _CLIENT_ID,
                "requested_token": "openai-api-key",
                "subject_token": id_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def refresh_token(refresh_tok: str) -> dict:
    """Refresh the OAuth token. Returns updated credential dict."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": _CLIENT_ID,
                "refresh_token": refresh_tok,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    new_api_key = await _obtain_api_key(data["id_token"])
    account_id = _extract_account_id(data["id_token"])
    return {
        "access_token": new_api_key,
        "refresh_token": data.get("refresh_token", refresh_tok),
        "id_token": data["id_token"],
        "account_id": account_id,
        "expires_at": int(time.time()) + data.get("expires_in", 3600),
    }


async def run_pkce_flow(on_url: Callable[[str], None]) -> dict:
    """
    Complete PKCE OAuth flow.

    Cancels any previously running flow first (so re-running /auth always works).
    Calls on_url(auth_url) once the server is bound and ready, then waits
    up to 5 minutes for the browser callback.

    Returns a credential dict ready to pass to credentials.write_oauth().
    """
    global _active_server, _active_future, _active_state

    # Cancel any existing in-flight flow cleanly before starting a new one
    await _close_active_server()

    verifier, challenge = _pkce_pair()
    state = _new_state()
    auth_url = build_auth_url(challenge, state)

    code_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

    server = await asyncio.start_server(
        _make_handler(state, code_future),
        "127.0.0.1",
        _CALLBACK_PORT,
    )
    _active_server = server
    _active_future = code_future
    _active_state = state

    logger.info("OAuth callback server ready on port %d", _CALLBACK_PORT)

    # Server is bound — safe to surface the URL now
    on_url(auth_url)

    try:
        code = await asyncio.wait_for(code_future, timeout=_CALLBACK_TIMEOUT)
    except asyncio.TimeoutError:
        await _close_active_server()
        raise TimeoutError("OAuth callback timed out — run /auth @openai again")
    finally:
        await _close_active_server()

    tokens = await _exchange_code(code, verifier)
    id_token = tokens.get("id_token", "")
    account_id = _extract_account_id(id_token)

    # Try to get an API-key style token via secondary exchange.
    # Fall back to the access_token from step 1 if not supported.
    try:
        api_key = await _obtain_api_key(id_token)
        logger.info("Secondary token exchange succeeded")
    except Exception as exc:
        logger.warning("Secondary token exchange failed (%s) — using access_token directly", exc)
        api_key = tokens.get("access_token", "")

    return {
        "access_token": api_key,
        "refresh_token": tokens.get("refresh_token", ""),
        "id_token": id_token,
        "account_id": account_id,
        "expires_at": int(time.time()) + tokens.get("expires_in", 3600),
    }
