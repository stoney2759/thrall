from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from services.mcp.manager import MCPClientManager


_manager: "MCPClientManager | None" = None


def set_manager(manager: "MCPClientManager") -> None:
    global _manager
    _manager = manager


async def execute(tool_name: str, args: dict[str, Any]) -> str:
    """
    Route an MCP tool call to the correct server client.
    tool_name format: 'server_name__tool_name' e.g. 'gmail__send_email'
    """
    if _manager is None:
        return "Error: MCP manager not initialised"

    from services.mcp.translator import parse_namespaced_tool
    try:
        server_name, bare_tool_name = parse_namespaced_tool(tool_name)
    except ValueError as e:
        return f"Error: {e}"

    client = _manager.get_client(server_name)
    if client is None:
        return f"Error: MCP server '{server_name}' not found"

    if not client.available:
        return f"Error: MCP server '{server_name}' is not available"

    return await client.call_tool(bare_tool_name, args)
