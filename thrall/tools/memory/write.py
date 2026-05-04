from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from schemas.memory import Episode, KnowledgeFact
from bootstrap import state


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    layer = call.args.get("layer", "episodic")
    content = call.args.get("content", "")
    tags = call.args.get("tags", [])

    try:
        from services.memory.router import get_store
        store = await get_store()

        if layer == "episodic":
            episode = Episode(
                session_id=state.get_session_id(),
                role="thrall",
                content=content,
                tags=tags,
            )
            allowed = await store.write_episode(episode)
            if not allowed:
                return _result(call.id, error="memory gate denied episode", start=start)
            return _result(call.id, output=f"episode written: {episode.id}", start=start)

        elif layer == "semantic":
            confidence = float(call.args.get("confidence", 1.0))
            source = call.args.get("source", "thrall")
            fact = KnowledgeFact(content=content, source=source, confidence=confidence, tags=tags)
            allowed = await store.write_fact(fact)
            if not allowed:
                return _result(call.id, error="memory gate denied fact", start=start)
            return _result(call.id, output=f"fact written: {fact.id}", start=start)

        else:
            return _result(call.id, error=f"unknown layer: {layer}", start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "memory_write"
DESCRIPTION = "Write to episodic or semantic memory. Goes through memory gate."
PARAMETERS = {
    "layer": {"type": "string", "required": False, "default": "episodic"},
    "content": {"type": "string", "required": True},
    "tags": {"type": "array", "items": {"type": "string"}, "required": False, "default": []},
    "confidence": {"type": "number", "required": False, "default": 1.0},
    "source": {"type": "string", "required": False, "default": "thrall"},
}
