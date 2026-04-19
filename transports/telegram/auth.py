from __future__ import annotations
from bootstrap import state


def is_allowed(user_id: int) -> bool:
    config = state.get_config()
    allowed: list = config.get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])

    # Empty list = no one allowed. Must explicitly add user IDs.
    if not allowed:
        return False

    return user_id in allowed or str(user_id) in [str(uid) for uid in allowed]


def add_user(user_id: int) -> None:
    config = state.get_config()
    tg = config.setdefault("transports", {}).setdefault("telegram", {})
    allowed: list = tg.setdefault("allowed_user_ids", [])
    if user_id not in allowed and str(user_id) not in [str(u) for u in allowed]:
        allowed.append(user_id)
