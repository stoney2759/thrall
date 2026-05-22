from __future__ import annotations
from pathlib import Path
from uuid import UUID
from schemas.message import Message, Role
from services import session_memory
from services.memory.router import get_store
from hooks import context_gate
from constants.memory import EPISODE_QUERY_LENGTH, MAX_EPISODES, MAX_FACTS

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

    return context_gate.build_context(
        session_context=session_ctx,
        episodes=episodes,
        facts=facts,
    )


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
