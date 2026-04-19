from __future__ import annotations
import json
import threading
from pathlib import Path
from scheduler.job import Job

_LOCK = threading.Lock()
_JOBS_PATH = Path(__file__).parent.parent / "state" / "jobs.json"


def _load_raw() -> list[dict]:
    if not _JOBS_PATH.exists():
        return []
    try:
        return json.loads(_JOBS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_raw(jobs: list[dict]) -> None:
    _JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _JOBS_PATH.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")


def load_jobs() -> list[Job]:
    with _LOCK:
        return [Job.from_dict(d) for d in _load_raw()]


def add_job(job: Job) -> None:
    with _LOCK:
        raw = _load_raw()
        raw.append(job.to_dict())
        _save_raw(raw)


def delete_job(job_id: str) -> bool:
    with _LOCK:
        raw = _load_raw()
        new = [d for d in raw if d["id"] != job_id]
        if len(new) == len(raw):
            return False
        _save_raw(new)
        return True


def update_last_run(job_id: str, ts: str) -> None:
    with _LOCK:
        raw = _load_raw()
        for d in raw:
            if d["id"] == job_id:
                d["last_run"] = ts
                break
        _save_raw(raw)
