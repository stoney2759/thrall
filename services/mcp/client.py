from __future__ import annotations
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

logger = logging.getLogger(__name__)

_TOOL_CALL_TIMEOUT = 30.0
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15 Thrall/1.0"
)


class MCPServerConfig:
    def __init__(
        self,
        name: str,
        transport: str,
        command: str = "",
        args: list[str] = None,
        env: dict[str, str] = None,
        url: str = "",
        headers: dict[str, str] = None,
        token_file: str = "",
        token_refresh_url: str = "",
    ):
        self.name = name
        self.token_refresh_url = token_refresh_url  # optional: POST {refresh_token} here when the token expires
        self.transport = transport
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.url = url
        self.headers = headers or {}
        self.token_file = token_file


class MCPClient:
    """
    Manages a single MCP server connection.
    Handles connect, tool discovery, tool execution, and basic crash recovery.
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session: ClientSession | None = None
        self._tools: list[Tool] = []
        self._available = False
        self._lock = asyncio.Lock()
        self._exit_stack = None

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def available(self) -> bool:
        return self._available

    @property
    def tools(self) -> list[Tool]:
        return self._tools

    async def _refresh_token(self, token: dict) -> dict | None:
        """Refresh an expired token via the server's token_refresh_url (if configured). Returns updated token or None."""
        import httpx
        refresh_token = token.get("refresh_token", "")
        if not refresh_token or not self.config.token_refresh_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    self.config.token_refresh_url,
                    json={"refresh_token": refresh_token},
                    headers={"User-Agent": _BROWSER_UA, "Content-Type": "application/json"},
                )
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "access_token": data["access_token"],
                        "refresh_token": data.get("refresh_token", refresh_token),
                        "expires_in": data.get("expires_in", 86400),
                        "obtained_at": time.time(),
                    }
        except Exception as e:
            logger.warning(f"MCP server '{self.name}': token refresh failed: {e}")
        return None

    async def _load_bearer_token(self) -> str | None:
        """Load Bearer token from token_file, refreshing if expired."""
        token_path = Path(self.config.token_file)
        if not token_path.exists():
            logger.warning(f"MCP server '{self.name}': token file not found ({self.config.token_file}) — sign in to this server and save its token there")
            return None
        try:
            token = json.loads(token_path.read_text())
            obtained_at = float(token.get("obtained_at", 0))
            expires_in = float(token.get("expires_in", 86400))
            if time.time() < obtained_at + expires_in - 60:
                return token["access_token"]

            logger.info(f"MCP server '{self.name}': token expired, attempting refresh")
            new_token = await self._refresh_token(token)
            if new_token:
                token_path.write_text(json.dumps(new_token, indent=2))
                logger.info(f"MCP server '{self.name}': token refreshed")
                return new_token["access_token"]

            logger.warning(f"MCP server '{self.name}': token expired and could not be refreshed — sign in to this server again")
            return None
        except Exception as e:
            logger.error(f"MCP server '{self.name}': failed to load token: {e}")
            return None

    async def connect(self) -> bool:
        """Connect to the MCP server and discover tools. Returns True on success."""
        import contextlib
        stack = contextlib.AsyncExitStack()
        await stack.__aenter__()
        success = False
        try:
            if self.config.transport == "stdio":
                import os
                merged_env = {**os.environ, **self.config.env}
                params = StdioServerParameters(
                    command=self.config.command,
                    args=self.config.args,
                    env=merged_env,
                )
                read, write = await stack.enter_async_context(stdio_client(params))

            elif self.config.transport in ("http", "streamable_http"):
                from mcp.client.streamable_http import streamablehttp_client

                effective_headers = dict(self.config.headers)
                effective_headers.setdefault("User-Agent", _BROWSER_UA)

                if self.config.token_file:
                    bearer = await self._load_bearer_token()
                    if bearer:
                        effective_headers["Authorization"] = f"Bearer {bearer}"
                    else:
                        logger.warning(f"MCP server '{self.name}': no valid token — connection will likely fail")

                read, write, _ = await stack.enter_async_context(
                    streamablehttp_client(self.config.url, headers=effective_headers or None)
                )

            elif self.config.transport == "sse":
                from mcp.client.sse import sse_client
                read, write = await stack.enter_async_context(
                    sse_client(self.config.url, headers=self.config.headers or None)
                )

            else:
                logger.warning(f"MCP server '{self.name}': transport '{self.config.transport}' not supported — skipping")
                return False

            self._session = await stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()

            result = await self._session.list_tools()
            self._tools = result.tools
            self._available = True
            self._exit_stack = stack
            success = True

            logger.info(f"MCP server '{self.name}' connected — {len(self._tools)} tools available")
            return True

        except BaseException as e:
            logger.error(f"MCP server '{self.name}' failed to connect: {type(e).__name__}: {e}")
            self._available = False
            return False

        finally:
            if not success:
                # Always close the stack on failure — this exits anyio cancel scopes
                # so they don't contaminate the rest of the event loop.
                try:
                    await stack.aclose()
                except BaseException:
                    pass

    async def disconnect(self) -> None:
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
        self._session = None
        self._available = False

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on this MCP server. Returns result as string."""
        if not self._available or not self._session:
            # Try reconnecting — token file may have been refreshed since startup
            logger.info(f"MCP server '{self.name}' offline, attempting reconnect before tool call")
            reconnected = await self.connect()
            if not reconnected:
                return f"Error: MCP server '{self.name}' is not available"

        async with self._lock:
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(tool_name, arguments),
                    timeout=_TOOL_CALL_TIMEOUT,
                )
                return _extract_text(result)

            except asyncio.TimeoutError:
                return f"Error: MCP server '{self.name}' tool '{tool_name}' timed out after {_TOOL_CALL_TIMEOUT}s"

            except Exception as e:
                logger.error(f"MCP server '{self.name}' tool '{tool_name}' error: {e}")
                # Attempt reconnect once
                logger.info(f"MCP server '{self.name}': attempting reconnect")
                await self.disconnect()
                reconnected = await self.connect()
                if reconnected:
                    try:
                        result = await asyncio.wait_for(
                            self._session.call_tool(tool_name, arguments),
                            timeout=_TOOL_CALL_TIMEOUT,
                        )
                        return _extract_text(result)
                    except Exception as e2:
                        return f"Error: MCP server '{self.name}' tool '{tool_name}' failed after reconnect: {e2}"
                return f"Error: MCP server '{self.name}' unavailable: {e}"


def _extract_text(result) -> str:
    """Convert MCP tool result content blocks to a plain string."""
    if not result or not result.content:
        return "(no output)"

    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif hasattr(block, "data"):
            parts.append(f"[binary data: {len(block.data)} bytes]")
        else:
            parts.append(str(block))

    return "\n".join(parts) if parts else "(no output)"
