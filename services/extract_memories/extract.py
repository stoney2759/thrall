from __future__ import annotations
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact
from services.llm import client as llm

_EXTRACTION_PROMPT = """You are a memory distillation system.
Given a set of conversation episodes, extract key facts, decisions, and patterns worth remembering long-term.
Return a JSON array of objects with fields: content (string), tags (list of strings), confidence (float 0-1).
Only extract facts that are genuinely useful to recall in future sessions. Be selective."""


async def extract_from_episodes(episodes: list[Episode], source: str) -> list[KnowledgeFact]:
    if not episodes:
        return []

    episode_text = "\n".join(
        f"[{e.timestamp.isoformat()}] {e.role}: {e.content}"
        for e in episodes
    )

    messages = [
        {"role": "system", "content": _EXTRACTION_PROMPT},
        {"role": "user", "content": episode_text},
    ]

    try:
        response = await llm.complete(messages)
        import json
        raw = json.loads(response)
        return [
            KnowledgeFact(
                content=item["content"],
                source=source,
                confidence=float(item.get("confidence", 1.0)),
                tags=item.get("tags", []),
            )
            for item in raw
            if isinstance(item, dict) and "content" in item
        ]
    except Exception:
        return []
