from __future__ import annotations
import re
from abc import ABC, abstractmethod
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact

_STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
    "how", "its", "may", "now", "off", "old", "own", "say", "she", "too",
    "use", "way", "who", "why", "did", "let", "put", "too", "big", "few",
    "got", "lot", "ago", "ago", "any", "far", "man", "ran", "run", "set",
    "was", "did", "been", "have", "that", "this", "they", "from", "with",
    "will", "what", "when", "then", "than", "also", "into", "over", "such",
    "just", "more", "some", "been", "each", "much", "very", "here", "like",
    "would", "could", "should", "about", "there", "their", "which", "other",
    "after", "where", "while", "these", "those", "being",
})


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
    async def list_facts(self, limit: int) -> list[KnowledgeFact]:
        """Most recent facts, newest last — used for the always-loaded user-memory block."""

    @abstractmethod
    async def delete_fact(self, fact_id: UUID) -> None: ...

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_ready(self) -> bool: ...

    # ── Search helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _query_keywords(query: str) -> list[str]:
        """Tokenize a query into significant keywords for fuzzy matching."""
        words = re.findall(r"\b\w{3,}\b", query.lower())
        keywords = [w for w in words if w not in _STOP_WORDS]
        return keywords if keywords else words
