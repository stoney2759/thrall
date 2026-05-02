from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from services.memory.router import get_store


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    layer = call.args.get("layer", "episodic")
    query = call.args.get("query", "")
    limit = call.args.get("limit", 20)

    try:
        store = await get_store()

        if layer == "episodic":
            episodes = await store.search_episodes(query, limit)
            results = _format_episodes(episodes)
        elif layer == "semantic":
            facts = await store.search_facts(query, limit)
            results = _format_facts(facts)
        else:
            return _result(call.id, error=f"unknown layer: {layer}", start=start)

        return _result(call.id, output=results or "no results", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _format_episodes(episodes: list) -> str:
    if not episodes:
        return "no matches"
    lines = [
        f"[{e.timestamp.strftime('%Y-%m-%d %H:%M')}] {e.role}: {e.content}"
        for e in episodes
    ]
    return "\n".join(lines)


def _format_facts(facts: list) -> str:
    if not facts:
        return "no matches"
    lines = [
        f"[{f.confidence:.0%}] {f.content} (tags: {', '.join(f.tags)})"
        for f in facts
    ]
    return "\n".join(lines)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "memory_read"
DESCRIPTION = "Read from episodic or semantic memory. Supports keyword search."
PARAMETERS = {
    "layer": {"type": "string", "required": False, "default": "episodic"},
    "query": {"type": "string", "required": False, "default": ""},
    "limit": {"type": "integer", "required": False, "default": 20},
}
