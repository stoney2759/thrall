from __future__ import annotations

# Stores the last exchange for each catalog agent profile so the next spawn
# can pick up the conversation where it left off.
# Keyed by profile name. Cleared once consumed.

_store: dict[str, dict] = {}


def save(profile: str, user_brief: str, agent_result: str) -> None:
    _store[profile] = {"brief": user_brief, "result": agent_result}


def pop(profile: str) -> dict | None:
    return _store.pop(profile, None)


def has(profile: str) -> bool:
    return profile in _store
