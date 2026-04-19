from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

logger = logging.getLogger(__name__)

_TOOL_CALL_TIMEOUT = 30.0


class MCPServerConfig:
    def __init__(self, name: str, transport: str, command: str, args: list[str], env: dict[str, str]):
        self.name = name
        self.transport = transport
        self.command = command
        self.args = args
        self.env = env


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

    async def connect(self) -> bool:
        """Connect to the MCP server and discover tools. Returns True on success."""
        try:
            if self.config.transport != "stdio":
                logger.warning(f"MCP server '{self.name}': transport '{self.config.transport}' not yet supported — skipping")
                return False

            import contextlib
            self._exit_stack = contextlib.AsyncExitStack()

            params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env or None,
            )

            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
            self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()

            result = await self._session.list_tools()
            self._tools = result.tools
            self._available = True

            logger.info(f"MCP server '{self.name}' connected — {len(self._tools)} tools available")
            return True

        except Exception as e:
            logger.error(f"MCP server '{self.name}' failed to connect: {e}")
            self._available = False
            return False

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
