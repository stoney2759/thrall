from __future__ import annotations
import threading
from pathlib import Path
from uuid import UUID
from schemas.memory import Episode, KnowledgeFact
from services.memory.backends.base import MemoryBackend


class JsonlBackend(MemoryBackend):
    """File-backed backend. Persists across restarts. No external services required."""

    def __init__(self, memory_dir: Path) -> None:
        self._episodes_path = memory_dir / "episodes" / "episodes.jsonl"
        self._facts_path = memory_dir / "knowledge" / "facts.jsonl"
        self._lock = threading.Lock()
        self._ready = False

    async def connect(self) -> None:
        self._episodes_path.parent.mkdir(parents=True, exist_ok=True)
        self._facts_path.parent.mkdir(parents=True, exist_ok=True)
        self._ready = True

    async def disconnect(self) -> None:
        self._ready = False

    def name(self) -> str:
        return "jsonl"

    def is_ready(self) -> bool:
        return self._ready

    # ── Episodes ──────────────────────────────────────────────────────────────

    async def write_episode(self, episode: Episode) -> None:
        with self._lock:
            with open(self._episodes_path, "a", encoding="utf-8") as f:
                f.write(episode.model_dump_json() + "\n")

    async def get_episodes(self, session_id: UUID, limit: int) -> list[Episode]:
        episodes = self._load_episodes()
        matches = [e for e in episodes if e.session_id == session_id]
        return matches[-limit:]

    async def search_episodes(self, query: str, limit: int) -> list[Episode]:
        episodes = self._load_episodes()
        q = query.lower()
        matches = [e for e in episodes if q in e.content.lower()]
        return matches[-limit:]

    def _load_episodes(self) -> list[Episode]:
        if not self._episodes_path.exists():
            return []
        episodes = []
        with open(self._episodes_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        episodes.append(Episode.model_validate_json(line))
                    except Exception:
                        pass
        return episodes

    # ── Knowledge ─────────────────────────────────────────────────────────────

    async def write_fact(self, fact: KnowledgeFact) -> None:
        with self._lock:
            with open(self._facts_path, "a", encoding="utf-8") as f:
                f.write(fact.model_dump_json() + "\n")

    async def search_facts(self, query: str, limit: int) -> list[KnowledgeFact]:
        facts = self._load_facts()
        q = query.lower()
        matches = [f for f in facts if q in f.content.lower()]
        return matches[-limit:]

    async def delete_fact(self, fact_id: UUID) -> None:
        facts = self._load_facts()
        remaining = [f for f in facts if f.id != fact_id]
        with self._lock:
            with open(self._facts_path, "w", encoding="utf-8") as f:
                for fact in remaining:
                    f.write(fact.model_dump_json() + "\n")

    def _load_facts(self) -> list[KnowledgeFact]:
        if not self._facts_path.exists():
            return []
        facts = []
        with open(self._facts_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        facts.append(KnowledgeFact.model_validate_json(line))
                    except Exception:
                        pass
        return facts
