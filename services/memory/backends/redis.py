from __future__ import annotations
import json
import logging
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact
from services.memory.backends.base import MemoryBackend

logger = logging.getLogger(__name__)

_EP_PREFIX = "thrall:ep:"
_EP_IDX = "thrall:ep:idx"


class RedisBackend(MemoryBackend):
    """Short-term episodic memory with TTL. Facts are not stored here — use Qdrant."""

    def __init__(self, url: str = "redis://localhost:6379", ttl_seconds: int = 604800) -> None:
        self._url = url
        self._ttl = ttl_seconds
        self._client = None
        self._ready = False

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(self._url, decode_responses=True)
            await self._client.ping()
            self._ready = True
            logger.info(f"Redis episodic backend connected: {self._url}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._ready = False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
        self._ready = False

    def name(self) -> str:
        return "redis"

    def is_ready(self) -> bool:
        return self._ready

    # ── Episodes ──────────────────────────────────────────────────────────────

    async def write_episode(self, episode: Episode) -> None:
        if not self._ready:
            return
        key = f"{_EP_PREFIX}{episode.id}"
        payload = {
            "id": str(episode.id),
            "session_id": str(episode.session_id),
            "role": episode.role,
            "content": episode.content,
            "tags": json.dumps(episode.tags),
            "timestamp": episode.timestamp.isoformat(),
        }
        await self._client.hset(key, mapping=payload)
        await self._client.expire(key, self._ttl)
        await self._client.zadd(_EP_IDX, {str(episode.id): episode.timestamp.timestamp()})

    async def get_episodes(self, session_id: UUID, limit: int) -> list[Episode]:
        if not self._ready:
            return []
        ids = await self._client.zrevrange(_EP_IDX, 0, limit * 5)
        episodes = []
        for ep_id in ids:
            ep = await self._fetch(ep_id)
            if ep and ep.session_id == session_id:
                episodes.append(ep)
            if len(episodes) >= limit:
                break
        return list(reversed(episodes))

    async def search_episodes(self, query: str, limit: int) -> list[Episode]:
        if not self._ready:
            return []
        ids = await self._client.zrevrange(_EP_IDX, 0, 300)
        q = query.lower()
        episodes = []
        for ep_id in ids:
            ep = await self._fetch(ep_id)
            if ep and (not q or q in ep.content.lower()):
                episodes.append(ep)
            if len(episodes) >= limit:
                break
        return list(reversed(episodes))

    async def _fetch(self, ep_id: str) -> Episode | None:
        key = f"{_EP_PREFIX}{ep_id}"
        data = await self._client.hgetall(key)
        if not data:
            await self._client.zrem(_EP_IDX, ep_id)
            return None
        try:
            from datetime import datetime, timezone
            return Episode(
                id=data["id"],
                session_id=data["session_id"],
                role=data["role"],
                content=data["content"],
                tags=json.loads(data.get("tags", "[]")),
                timestamp=datetime.fromisoformat(data["timestamp"]),
            )
        except Exception:
            return None

    # ── Facts — not stored here ───────────────────────────────────────────────

    async def write_fact(self, fact: KnowledgeFact) -> None:
        pass

    async def search_facts(self, query: str, limit: int) -> list[KnowledgeFact]:
        return []

    async def delete_fact(self, fact_id: UUID) -> None:
        pass
