from __future__ import annotations
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact
from services.memory.backends.base import MemoryBackend

# STRUCTURED PERSISTENT MEMORY — episodes + facts with full query capability
# PostgreSQL stores the durable record of everything Thrall remembers.
# Redis caches the hot recent slice. Qdrant indexes the semantic vectors.
#
# TODO: implement when postgres is provisioned
# Deps: pip install asyncpg
# Config: memory.postgres.url in config.toml
#
# Schema (reference — create via migration):
#   episodes(id UUID PK, session_id UUID, role TEXT, content TEXT, tags TEXT[], timestamp TIMESTAMPTZ)
#   facts(id UUID PK, content TEXT, source TEXT, confidence FLOAT, tags TEXT[], created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)


class PostgresBackend(MemoryBackend):
    def __init__(self, url: str = "postgresql://localhost/thrall") -> None:
        self._url = url
        self._pool = None
        self._ready = False

    async def connect(self) -> None:
        raise NotImplementedError("PostgresBackend not yet implemented")

    async def disconnect(self) -> None:
        raise NotImplementedError("PostgresBackend not yet implemented")

    def name(self) -> str:
        return "postgres"

    def is_ready(self) -> bool:
        return self._ready

    async def write_episode(self, episode: Episode) -> None:
        raise NotImplementedError

    async def get_episodes(self, session_id: UUID, limit: int) -> list[Episode]:
        raise NotImplementedError

    async def search_episodes(self, query: str, limit: int) -> list[Episode]:
        raise NotImplementedError

    async def write_fact(self, fact: KnowledgeFact) -> None:
        raise NotImplementedError

    async def search_facts(self, query: str, limit: int) -> list[KnowledgeFact]:
        raise NotImplementedError

    async def delete_fact(self, fact_id: UUID) -> None:
        raise NotImplementedError
