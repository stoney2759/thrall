from __future__ import annotations
import json
import logging
from pathlib import Path
from uuid import UUID
from schemas.task import TaskStatus

logger = logging.getLogger(__name__)

_RESULTS_PATH = Path(__file__).parent.parent.parent / "state" / "task_results.jsonl"
_results: dict[UUID, dict] = {}
_loaded = False


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    if not _RESULTS_PATH.exists():
        return
    try:
        for line in _RESULTS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                _results[UUID(entry["task_id"])] = entry
    except Exception as e:
        logger.warning(f"Failed to load task results from disk: {e}")


def set_result(task_id: UUID, status: TaskStatus, result: str | None, error: str | None) -> None:
    _ensure_loaded()
    entry = {
        "task_id": str(task_id),
        "status": status.value,
        "result": result,
        "error": error,
    }
    _results[task_id] = entry
    _persist(entry)


def get_result(task_id: UUID) -> dict | None:
    _ensure_loaded()
    return _results.get(task_id)


def all_results() -> list[dict]:
    _ensure_loaded()
    return list(_results.values())


def clear(task_id: UUID) -> None:
    _ensure_loaded()
    _results.pop(task_id, None)


def _persist(entry: dict) -> None:
    try:
        _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_RESULTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to persist task result {entry.get('task_id')}: {e}")
