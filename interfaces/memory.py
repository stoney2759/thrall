from __future__ import annotations
from abc import ABC, abstractmethod
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact


class MemoryStore(ABC):
    @abstractmethod
    async def write_episode(self, episode: Episode) -> None: ...

    @abstractmethod
    async def search_episodes(self, query: str, limit: int) -> list[Episode]: ...

    @abstractmethod
    async def write_fact(self, fact: KnowledgeFact) -> None: ...

    @abstractmethod
    async def search_facts(self, query: str, limit: int) -> list[KnowledgeFact]: ...

    @abstractmethod
    async def get_session_episodes(self, session_id: UUID) -> list[Episode]: ...
