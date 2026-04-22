from __future__ import annotations
import json
import time
from pathlib import Path
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from schemas.memory import Episode, KnowledgeFact

_MEMORY_DIR = Path(__file__).parent.parent.parent.parent / "memory"


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    layer = call.args.get("layer", "episodic")
    query = call.args.get("query", "")
    limit = call.args.get("limit", 20)

    try:
        if layer == "episodic":
            results = _read_episodes(query, limit)
        elif layer == "semantic":
            results = _read_facts(query, limit)
        else:
            return _result(call.id, error=f"unknown layer: {layer}", start=start)

        return _result(call.id, output=results or "no results", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _read_episodes(query: str, limit: int) -> str:
    path = _MEMORY_DIR / "episodes" / "episodes.jsonl"
    if not path.exists():
        return "no episodes"
    episodes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = Episode.model_validate_json(line)
            if not query or query.lower() in e.content.lower():
                episodes.append(f"[{e.timestamp.strftime('%Y-%m-%d %H:%M')}] {e.role}: {e.content}")
        except Exception:
            continue
    return "\n".join(episodes[-limit:]) if episodes else "no matches"


def _read_facts(query: str, limit: int) -> str:
    path = _MEMORY_DIR / "knowledge" / "facts.jsonl"
    if not path.exists():
        return "no facts"
    facts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            f = KnowledgeFact.model_validate_json(line)
            if not query or query.lower() in f.content.lower():
                facts.append(f"[{f.confidence:.0%}] {f.content} (tags: {', '.join(f.tags)})")
        except Exception:
            continue
    return "\n".join(facts[-limit:]) if facts else "no matches"


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "memory.read"
DESCRIPTION = "Read from episodic or semantic memory. Supports keyword search."
PARAMETERS = {
    "layer": {"type": "string", "required": False, "default": "episodic"},
    "query": {"type": "string", "required": False, "default": ""},
    "limit": {"type": "integer", "required": False, "default": 20},
}
