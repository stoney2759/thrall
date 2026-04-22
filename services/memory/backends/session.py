from __future__ import annotations
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact
from services.memory.backends.base import MemoryBackend


class SessionBackend(MemoryBackend):
    """In-memory backend. Active now. No persistence — dies with the process."""

    def __init__(self) -> None:
        self._episodes: list[Episode] = []
        self._facts: list[KnowledgeFact] = []
        self._ready = False

    async def connect(self) -> None:
        self._ready = True

    async def disconnect(self) -> None:
        self._ready = False

    def name(self) -> str:
        return "session"

    def is_ready(self) -> bool:
        return self._ready

    # ── Episodes ──────────────────────────────────────────────────────────────

    async def write_episode(self, episode: Episode) -> None:
        self._episodes.append(episode)

    async def get_episodes(self, session_id: UUID, limit: int) -> list[Episode]:
        matches = [e for e in self._episodes if e.session_id == session_id]
        return matches[-limit:]

    async def search_episodes(self, query: str, limit: int) -> list[Episode]:
        q = query.lower()
        matches = [e for e in self._episodes if q in e.content.lower()]
        return matches[-limit:]

    # ── Knowledge ─────────────────────────────────────────────────────────────

    async def write_fact(self, fact: KnowledgeFact) -> None:
        self._facts.append(fact)

    async def search_facts(self, query: str, limit: int) -> list[KnowledgeFact]:
        q = query.lower()
        matches = [f for f in self._facts if q in f.content.lower()]
        return matches[-limit:]

    async def delete_fact(self, fact_id: UUID) -> None:
        self._facts = [f for f in self._facts if f.id != fact_id]
