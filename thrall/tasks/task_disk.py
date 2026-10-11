"""Shared disk persistence for task state — readable by all processes."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

_TASKS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "state", "tasks.json")
_TTL_SECONDS = 60


def write(
    task_id: str,
    profile: str,
    status: str,
    brief: str,
    created_at: str,
    completed_at: str | None = None,
) -> None:
    os.makedirs(os.path.dirname(_TASKS_FILE), exist_ok=True)
    try:
        with open(_TASKS_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data[task_id] = {
        "id": task_id,
        "profile": profile,
        "status": status,
        "brief": brief,
        "created_at": created_at,
        "completed_at": completed_at,
    }

    now = datetime.now(timezone.utc)
    data = {
        k: v for k, v in data.items()
        if v.get("completed_at") is None
        or (now - datetime.fromisoformat(v["completed_at"])).total_seconds() < _TTL_SECONDS
    }

    tmp = _TASKS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _TASKS_FILE)


def read_all() -> list[dict]:
    try:
        with open(_TASKS_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    now = datetime.now(timezone.utc)
    return [
        v for v in data.values()
        if v.get("completed_at") is None
        or (now - datetime.fromisoformat(v["completed_at"])).total_seconds() < _TTL_SECONDS
    ]
