from __future__ import annotations
from bootstrap import state
from schemas.message import Transport


def is_authorised(user_id: str, transport: Transport) -> bool:
    config = state.get_config()

    if transport in (Transport.CLI, Transport.SCHEDULER):
        return True

    transport_config = config.get("transports", {}).get(transport.value, {})
    allowed: list[str | int] = transport_config.get("allowed_user_ids", [])

    if not allowed:
        return False

    return str(user_id) in [str(uid) for uid in allowed]


def add_allowed_user(user_id: str, transport: Transport) -> None:
    config = state.get_config()
    transport_config = config.setdefault("transports", {}).setdefault(transport.value, {})
    allowed: list = transport_config.setdefault("allowed_user_ids", [])
    if str(user_id) not in [str(uid) for uid in allowed]:
        allowed.append(str(user_id))
