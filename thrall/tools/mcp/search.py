from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from services import session_memory
from constants.tools import MCP_SEARCH_MAX_RESULTS, MCP_SESSION_TOOL_CAP


def execute(call: ToolCall) -> ToolResult:
    # registry imports this module, so registry is imported at call time (not a dynamic import)
    from thrall.tools import registry

    start = time.monotonic()
    query = str(call.args.get("query", "")).strip()
    if not query:
        return _result(call.id, start, error="query is required — e.g. 'photocraft open save' or 'select:deckcraft__export'")

    # Only server names, no task words: any tools loaded would be an arbitrary slice, so give an overview
    terms = query.lower().split()
    servers = registry.mcp_servers()
    if not query.lower().startswith("select:") and all(t in servers for t in terms):
        overview = "\n".join(registry.mcp_server_overview(t) for t in dict.fromkeys(terms))
        return _result(call.id, start, output=(
            f"Nothing loaded — '{query}' only names a server. Add what you want to do, "
            f"e.g. '{terms[0]} <task words>', to load matching tools.\n{overview}"
        ))

    found = registry.search_mcp(query, MCP_SEARCH_MAX_RESULTS)
    if not found:
        return _result(call.id, start, output=(
            f"No MCP tools matched '{query}'. Available servers:\n{registry.mcp_catalog() or '(none connected)'}"
        ))

    added = session_memory.load_mcp_tools(call.session_id, found, MCP_SESSION_TOOL_CAP)
    lines = [f"Loaded {len(found)} tool(s) — callable now ({len(added)} new this session):"]
    lines.extend(f"- {registry.mcp_tool_summary(name)}" for name in found)
    return _result(call.id, start, output="\n".join(lines))


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "mcp_search"
DESCRIPTION = (
    "Find and load tools from connected MCP servers (they are hidden until loaded). "
    "Query with keywords — server name plus what you want to do, e.g. 'deckcraft new slide export' — "
    "or 'select:server__tool,server__tool' for exact names. Loaded tools become callable immediately "
    "and stay loaded while in use; tools unused for a while are unloaded — search again if one is missing."
)
PARAMETERS = {
    "query": {"type": "string", "required": True},
}
