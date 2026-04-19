from __future__ import annotations
import logging
from typing import Any

from services.mcp.client import MCPClient, MCPServerConfig
from services.mcp.translator import mcp_tool_to_thrall

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Manages all configured MCP server connections.
    Loaded at startup from config.toml [[mcp.servers]] entries.
    """

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}

    async def connect_all(self, mcp_config: dict) -> None:
        """
        Connect to all enabled MCP servers from config.
        Failures are logged but never crash startup.
        """
        if not mcp_config.get("enabled", True):
            logger.info("MCP disabled in config — skipping all servers")
            return

        servers = mcp_config.get("servers", [])
        if not servers:
            logger.info("No MCP servers configured")
            return

        for server_cfg in servers:
            if not server_cfg.get("enabled", True):
                logger.info(f"MCP server '{server_cfg.get('name', '?')}' disabled — skipping")
                continue

            config = MCPServerConfig(
                name=server_cfg["name"],
                transport=server_cfg.get("transport", "stdio"),
                command=server_cfg["command"],
                args=server_cfg.get("args", []),
                env=server_cfg.get("env", {}),
            )

            client = MCPClient(config)
            success = await client.connect()
            self._clients[config.name] = client

            if not success:
                logger.warning(f"MCP server '{config.name}' unavailable at startup — will retry on next use")

    async def disconnect_all(self) -> None:
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()

    def get_client(self, server_name: str) -> MCPClient | None:
        return self._clients.get(server_name)

    def available_servers(self) -> list[str]:
        return [name for name, c in self._clients.items() if c.available]

    def known_server_names(self) -> set[str]:
        return set(self._clients.keys())

    def all_tools(self) -> list[dict]:
        """
        Return all tool definitions from all connected servers in Thrall format.
        Called at startup to populate the tool registry.
        """
        tool_defs = []
        for client in self._clients.values():
            if not client.available:
                continue
            for tool in client.tools:
                tool_defs.append(mcp_tool_to_thrall(client.name, tool))
        return tool_defs

    def status_report(self) -> str:
        if not self._clients:
            return "No MCP servers configured."
        lines = ["MCP Servers:"]
        for name, client in self._clients.items():
            status = "online" if client.available else "offline"
            tool_count = len(client.tools) if client.available else 0
            lines.append(f"  {name}: {status} ({tool_count} tools)")
        return "\n".join(lines)
