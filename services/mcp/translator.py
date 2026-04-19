from __future__ import annotations
from mcp.types import Tool


def mcp_tool_to_thrall(server_name: str, tool: Tool) -> dict:
    """
    Translate an MCP tool definition into Thrall's tool definition format.
    Tool name is namespaced: gmail.send_email, github.create_pr, etc.
    """
    namespaced_name = f"{server_name}.{tool.name}"

    # MCP inputSchema is already JSON Schema — pass through directly
    parameters = {}
    if tool.inputSchema:
        schema = tool.inputSchema
        if hasattr(schema, "model_dump"):
            parameters = schema.model_dump(exclude_none=True)
        elif isinstance(schema, dict):
            parameters = schema
        else:
            parameters = {"type": "object", "properties": {}}
    else:
        parameters = {"type": "object", "properties": {}}

    description = tool.description or f"Tool '{tool.name}' from MCP server '{server_name}'"

    return {
        "type": "function",
        "function": {
            "name": namespaced_name,
            "description": description,
            "parameters": parameters,
        },
    }


def parse_namespaced_tool(tool_name: str) -> tuple[str, str]:
    """
    Split 'gmail.send_email' → ('gmail', 'send_email').
    Raises ValueError if not namespaced.
    """
    parts = tool_name.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Not a namespaced MCP tool: '{tool_name}'")
    return parts[0], parts[1]


def is_mcp_tool(tool_name: str, known_servers: set[str]) -> bool:
    """Return True if tool_name looks like an MCP tool from a known server."""
    parts = tool_name.split(".", 1)
    return len(parts) == 2 and parts[0] in known_servers
