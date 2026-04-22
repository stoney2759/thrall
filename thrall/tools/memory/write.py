from __future__ import annotations
import time
from pathlib import Path
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from schemas.memory import Episode, KnowledgeFact
from hooks import memory_gate
from bootstrap import state

_MEMORY_DIR = Path(__file__).parent.parent.parent.parent / "memory"


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    layer = call.args.get("layer", "episodic")
    content = call.args.get("content", "")
    tags = call.args.get("tags", [])

    try:
        if layer == "episodic":
            return _write_episode(call.id, content, tags, start)
        elif layer == "semantic":
            confidence = float(call.args.get("confidence", 1.0))
            source = call.args.get("source", "thrall")
            return _write_fact(call.id, content, tags, confidence, source, start)
        else:
            return _result(call.id, error=f"unknown layer: {layer}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _write_episode(call_id: UUID, content: str, tags: list, start: float) -> ToolResult:
    episode = Episode(
        session_id=state.get_session_id(),
        role="thrall",
        content=content,
        tags=tags,
    )
    gate = memory_gate.check_episode(episode)
    if not gate.allowed:
        return _result(call_id, error=f"memory gate denied: {gate.reason}", start=start)

    path = _MEMORY_DIR / "episodes" / "episodes.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(episode.model_dump_json() + "\n")
    return _result(call_id, output=f"episode written: {episode.id}", start=start)


def _write_fact(call_id: UUID, content: str, tags: list, confidence: float, source: str, start: float) -> ToolResult:
    fact = KnowledgeFact(content=content, source=source, confidence=confidence, tags=tags)
    gate = memory_gate.check_fact(fact)
    if not gate.allowed:
        return _result(call_id, error=f"memory gate denied: {gate.reason}", start=start)

    path = _MEMORY_DIR / "knowledge" / "facts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(fact.model_dump_json() + "\n")
    return _result(call_id, output=f"fact written: {fact.id}", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "memory.write"
DESCRIPTION = "Write to episodic or semantic memory. Goes through memory gate."
PARAMETERS = {
    "layer": {"type": "string", "required": False, "default": "episodic"},
    "content": {"type": "string", "required": True},
    "tags": {"type": "array", "required": False, "default": []},
    "confidence": {"type": "number", "required": False, "default": 1.0},
    "source": {"type": "string", "required": False, "default": "thrall"},
}
