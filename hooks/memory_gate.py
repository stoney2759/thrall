from __future__ import annotations
from dataclasses import dataclass
from schemas.memory import Episode, KnowledgeFact
from hooks import audit

_MIN_EPISODE_LENGTH = 10
_MAX_EPISODE_LENGTH = 8_000
_MIN_FACT_CONFIDENCE = 0.5

# Tags that signal content should not be persisted
_EPHEMERAL_TAGS: set[str] = {"ephemeral", "temp", "session-only", "do-not-persist"}


@dataclass
class MemoryGateResult:
    allowed: bool
    reason: str | None = None


def check_episode(episode: Episode) -> MemoryGateResult:
    if len(episode.content.strip()) < _MIN_EPISODE_LENGTH:
        audit.log_deny("memory_gate", reason="episode too short to persist")
        return MemoryGateResult(allowed=False, reason="too short")

    if len(episode.content) > _MAX_EPISODE_LENGTH:
        audit.log_deny("memory_gate", reason="episode exceeds max length")
        return MemoryGateResult(allowed=False, reason="too long")

    if _EPHEMERAL_TAGS.intersection(set(episode.tags)):
        audit.log_deny("memory_gate", reason="episode tagged ephemeral")
        return MemoryGateResult(allowed=False, reason="ephemeral tag")

    audit.log_allow("memory_gate", reason="episode approved for episodic store")
    return MemoryGateResult(allowed=True)


def check_fact(fact: KnowledgeFact) -> MemoryGateResult:
    if fact.confidence < _MIN_FACT_CONFIDENCE:
        audit.log_deny("memory_gate", reason=f"fact confidence {fact.confidence} below threshold")
        return MemoryGateResult(allowed=False, reason="low confidence")

    if not fact.content.strip():
        audit.log_deny("memory_gate", reason="empty fact content")
        return MemoryGateResult(allowed=False, reason="empty content")

    if _EPHEMERAL_TAGS.intersection(set(fact.tags)):
        audit.log_deny("memory_gate", reason="fact tagged ephemeral")
        return MemoryGateResult(allowed=False, reason="ephemeral tag")

    audit.log_allow("memory_gate", reason="fact approved for knowledge store")
    return MemoryGateResult(allowed=True)
