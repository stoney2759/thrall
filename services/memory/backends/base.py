from __future__ import annotations
from abc import ABC, abstractmethod
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact


class MemoryBackend(ABC):
    """ABC for all memory backends. Becomes a Rust trait at port time."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    # ── Episodes ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def write_episode(self, episode: Episode) -> None: ...

    @abstractmethod
    async def get_episodes(self, session_id: UUID, limit: int) -> list[Episode]: ...

    @abstractmethod
    async def search_episodes(self, query: str, limit: int) -> list[Episode]: ...

    # ── Knowledge ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def write_fact(self, fact: KnowledgeFact) -> None: ...

    @abstractmethod
    async def search_facts(self, query: str, limit: int) -> list[KnowledgeFact]: ...

    @abstractmethod
    async def delete_fact(self, fact_id: UUID) -> None: ...

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_ready(self) -> bool: ...
