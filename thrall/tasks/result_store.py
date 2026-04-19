from __future__ import annotations
from uuid import UUID
from schemas.task import TaskStatus

# In-memory result store — keyed by task ID.
# Thrall uses agents.result to poll these.

_results: dict[UUID, dict] = {}


def set_result(task_id: UUID, status: TaskStatus, result: str | None, error: str | None) -> None:
    _results[task_id] = {
        "task_id": str(task_id),
        "status": status.value,
        "result": result,
        "error": error,
    }


def get_result(task_id: UUID) -> dict | None:
    return _results.get(task_id)


def all_results() -> list[dict]:
    return list(_results.values())


def clear(task_id: UUID) -> None:
    _results.pop(task_id, None)
