from __future__ import annotations
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact
from services.memory.backends.base import MemoryBackend
from hooks import memory_gate

# Episodes → episode_backend (Redis or session)
# Facts    → fact_backend   (Qdrant or session)
# Nothing else changes — router.py wires the backends, nothing downstream cares.


class MemoryStore:
    def __init__(self, episode_backend: MemoryBackend, fact_backend: MemoryBackend) -> None:
        self._episode_backend = episode_backend
        self._fact_backend = fact_backend

    async def write_episode(self, episode: Episode) -> bool:
        result = memory_gate.check_episode(episode)
        if not result.allowed:
            return False
        await self._episode_backend.write_episode(episode)
        return True

    async def write_fact(self, fact: KnowledgeFact) -> bool:
        result = memory_gate.check_fact(fact)
        if not result.allowed:
            return False
        await self._fact_backend.write_fact(fact)
        return True

    async def get_episodes(self, session_id: UUID, limit: int = 50) -> list[Episode]:
        return await self._episode_backend.get_episodes(session_id, limit)

    async def search_episodes(self, query: str, limit: int = 20) -> list[Episode]:
        return await self._episode_backend.search_episodes(query, limit)

    async def search_facts(self, query: str, limit: int = 10) -> list[KnowledgeFact]:
        return await self._fact_backend.search_facts(query, limit)

    async def delete_fact(self, fact_id: UUID) -> None:
        await self._fact_backend.delete_fact(fact_id)

    def backend_names(self) -> tuple[str, str]:
        return self._episode_backend.name(), self._fact_backend.name()

    def is_ready(self) -> bool:
        return self._episode_backend.is_ready() and self._fact_backend.is_ready()
