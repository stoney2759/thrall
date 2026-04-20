from __future__ import annotations
import logging
from bootstrap import state
from services.memory.backends.base import MemoryBackend
from services.memory.store import MemoryStore

logger = logging.getLogger(__name__)

_store: MemoryStore | None = None


async def get_store() -> MemoryStore:
    global _store
    if _store is not None and _store.is_ready():
        return _store
    _store = await _build_store()
    return _store


async def _build_store() -> MemoryStore:
    config = state.get_config().get("memory", {})
    episode_backend = await _build_episode_backend(config)
    fact_backend = await _build_fact_backend(config)
    return MemoryStore(episode_backend, fact_backend)


async def _build_episode_backend(config: dict) -> MemoryBackend:
    import os
    name = os.environ.get("THRALL_EPISODE_BACKEND") or config.get("episode_backend", "session")
    if name == "redis":
        try:
            from services.memory.backends.redis import RedisBackend
            ttl_seconds = config.get("episodic_ttl_days", 7) * 86400
            backend = RedisBackend(
                url=config.get("redis", {}).get("url", "redis://localhost:6379"),
                ttl_seconds=ttl_seconds,
            )
            await backend.connect()
            if backend.is_ready():
                return backend
            logger.warning("Redis unavailable — falling back to session backend for episodes")
        except Exception as e:
            logger.warning(f"Redis backend failed to initialise: {e} — falling back to session")

    from services.memory.backends.session import SessionBackend
    backend = SessionBackend()
    await backend.connect()
    return backend


async def _build_fact_backend(config: dict) -> MemoryBackend:
    import os
    name = os.environ.get("THRALL_FACT_BACKEND") or config.get("fact_backend", "session")
    if name == "qdrant":
        try:
            from services.memory.backends.qdrant import QdrantBackend
            backend = QdrantBackend(
                url=config.get("qdrant", {}).get("url", "http://localhost:6333"),
            )
            await backend.connect()
            if backend.is_ready():
                return backend
            logger.warning("Qdrant unavailable — falling back to session backend for facts")
        except Exception as e:
            logger.warning(f"Qdrant backend failed to initialise: {e} — falling back to session")

    from services.memory.backends.session import SessionBackend
    backend = SessionBackend()
    await backend.connect()
    return backend
