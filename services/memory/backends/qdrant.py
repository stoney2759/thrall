from __future__ import annotations
import logging
import os
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact
from services.memory.backends.base import MemoryBackend

logger = logging.getLogger(__name__)

_FACTS_COLLECTION = "thrall_facts"
_EMBED_MODEL = "text-embedding-3-small"
_EMBED_DIM = 512


class QdrantBackend(MemoryBackend):
    """Long-term semantic memory via vector search. Episodes not stored here — use Redis."""

    def __init__(self, url: str = "http://localhost:6333") -> None:
        self._url = url
        self._client = None
        self._openai = None
        self._ready = False

    async def connect(self) -> None:
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, VectorParams
            from openai import AsyncOpenAI

            self._client = AsyncQdrantClient(url=self._url)
            self._openai = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            collections = await self._client.get_collections()
            existing = {c.name for c in collections.collections}
            if _FACTS_COLLECTION not in existing:
                await self._client.create_collection(
                    collection_name=_FACTS_COLLECTION,
                    vectors_config=VectorParams(size=_EMBED_DIM, distance=Distance.COSINE),
                )

            self._ready = True
            logger.info(f"Qdrant semantic backend connected: {self._url}")
        except Exception as e:
            logger.warning(f"Qdrant connection failed: {e}")
            self._ready = False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
        self._ready = False

    def name(self) -> str:
        return "qdrant"

    def is_ready(self) -> bool:
        return self._ready

    async def _embed(self, text: str) -> list[float]:
        response = await self._openai.embeddings.create(
            model=_EMBED_MODEL,
            input=text[:8000],
            dimensions=_EMBED_DIM,
        )
        return response.data[0].embedding

    # ── Facts ─────────────────────────────────────────────────────────────────

    async def write_fact(self, fact: KnowledgeFact) -> None:
        if not self._ready:
            return
        from qdrant_client.models import PointStruct
        try:
            vector = await self._embed(fact.content)
            await self._client.upsert(
                collection_name=_FACTS_COLLECTION,
                points=[PointStruct(
                    id=str(fact.id),
                    vector=vector,
                    payload={
                        "content": fact.content,
                        "source": fact.source,
                        "confidence": fact.confidence,
                        "tags": fact.tags,
                        "created_at": fact.created_at.isoformat(),
                        "updated_at": fact.updated_at.isoformat(),
                    },
                )],
            )
        except Exception as e:
            logger.error(f"Qdrant write_fact failed: {e}")

    async def search_facts(self, query: str, limit: int) -> list[KnowledgeFact]:
        if not self._ready:
            return []
        try:
            vector = await self._embed(query)
            results = await self._client.search(
                collection_name=_FACTS_COLLECTION,
                query_vector=vector,
                limit=limit,
                score_threshold=0.5,
            )
            facts = []
            for r in results:
                p = r.payload
                facts.append(KnowledgeFact(
                    id=r.id,
                    content=p["content"],
                    source=p.get("source", "thrall"),
                    confidence=float(p.get("confidence", 1.0)),
                    tags=p.get("tags", []),
                    created_at=p.get("created_at"),
                    updated_at=p.get("updated_at"),
                ))
            return facts
        except Exception as e:
            logger.error(f"Qdrant search_facts failed: {e}")
            return []

    async def delete_fact(self, fact_id: UUID) -> None:
        if not self._ready:
            return
        try:
            from qdrant_client.models import PointIdsList
            await self._client.delete(
                collection_name=_FACTS_COLLECTION,
                points_selector=PointIdsList(points=[str(fact_id)]),
            )
        except Exception as e:
            logger.error(f"Qdrant delete_fact failed: {e}")

    # ── Episodes — not stored here ────────────────────────────────────────────

    async def write_episode(self, episode: Episode) -> None:
        pass

    async def get_episodes(self, session_id: UUID, limit: int) -> list[Episode]:
        return []

    async def search_episodes(self, query: str, limit: int) -> list[Episode]:
        return []
