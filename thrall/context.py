from __future__ import annotations
from pathlib import Path
from uuid import UUID
from schemas.message import Message, Role
from schemas.memory import KnowledgeFact
from services import session_memory
from services.memory.router import get_store
from hooks import context_gate
from constants.memory import (
    EPISODE_QUERY_LENGTH, MAX_EPISODES, MAX_FACTS,
    USER_FACT_SOURCE_MARKER, USER_FACTS_SCAN, USER_FACTS_MAX, USER_FACTS_MAX_CHARS,
)

_IDENTITY_DIR = Path(__file__).parent.parent / "identity"


async def assemble(message: Message) -> list[dict]:
    """Build the full message list for a reasoning turn.
    Order: system (soul + identity) → knowledge → episodes → session context."""

    # Hot session context
    session_ctx = session_memory.get_context(message.session_id)

    # Pull relevant memory from store
    store = await get_store()
    query = message.content[:EPISODE_QUERY_LENGTH]
    episodes = await store.search_episodes(query, limit=MAX_EPISODES)
    facts = await store.search_facts(query, limit=MAX_FACTS)
    user_facts = select_user_facts(await store.list_facts(USER_FACTS_SCAN))
    user_ids = {f.id for f in user_facts}

    return context_gate.build_context(
        session_context=session_ctx,
        episodes=episodes,
        facts=[f for f in facts if f.id not in user_ids],
        user_facts=user_facts,
    )


def select_user_facts(facts: list[KnowledgeFact]) -> list[KnowledgeFact]:
    """Facts the user gave Thrall, newest kept, within USER_FACTS_MAX and USER_FACTS_MAX_CHARS. Oldest first."""
    mine = [f for f in facts if USER_FACT_SOURCE_MARKER in (f.source or "").lower()][-USER_FACTS_MAX:]
    kept: list[KnowledgeFact] = []
    total = 0
    for fact in reversed(mine):
        total += len(fact.content) + 3
        if total > USER_FACTS_MAX_CHARS:
            break
        kept.append(fact)
    return list(reversed(kept))


def load_identity() -> str | None:
    from bootstrap import state
    soul = _read_file("SOUL.md")
    identity = _read_file("IDENTITY.md")
    agents = _read_file("AGENTS.md")
    tools = _read_file("TOOLS.md")
    personality = state.get_active_profile_content()
    parts = [p for p in [soul, identity, agents, tools, personality] if p]
    return "\n\n".join(parts) if parts else None


def _read_file(filename: str) -> str | None:
    path = _IDENTITY_DIR / filename
    return path.read_text(encoding="utf-8").strip() if path.exists() else None
