"""Connect to MCP servers once per process.

The Telegram bot and the API server both need MCP tools. When they run in the same process
(thrall.py "Webapp + Telegram"), starting MCP from each would launch every server twice, so
both call `start()` here and only the first call connects.
"""
from __future__ import annotations
import asyncio
import logging
from bootstrap import state

logger = logging.getLogger(__name__)

_manager = None
_lock = asyncio.Lock()


async def start() -> None:
    """Connect all enabled MCP servers and register their tools (no-op if already started)."""
    global _manager
    async with _lock:
        if _manager is not None:
            return
        try:
            from services.mcp.manager import MCPClientManager
            from services.mcp import executor as mcp_executor
            from thrall.tools import registry as tools
            manager = MCPClientManager()
            await manager.connect_all(state.get_config().get("mcp", {}))
            mcp_executor.set_manager(manager)
            _manager = manager
            mcp_tools = manager.all_tools()
            if mcp_tools:
                tools.register_mcp_tools(mcp_tools)
                state.log_error(f"MCP: registered {len(mcp_tools)} tools from {manager.available_servers()}")
        except BaseException as e:  # MCP must never stop Thrall starting
            logger.error("MCP startup error: %s: %s", type(e).__name__, e)
            state.log_error(f"MCP startup error: {type(e).__name__}: {e}")


async def stop() -> None:
    global _manager
    async with _lock:
        if _manager is None:
            return
        try:
            await _manager.disconnect_all()
        except BaseException as e:
            logger.debug("MCP shutdown noise: %s", e)
        _manager = None
