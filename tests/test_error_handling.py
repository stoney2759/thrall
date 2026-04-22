from __future__ import annotations
import json
import pytest
from pathlib import Path
from uuid import uuid4
from schemas.task import TaskStatus
from thrall.tools.filesystem._resolve import is_protected, filter_protected


# ── RESULT STORE PERSISTENCE ──────────────────────────────────────────────────

class TestResultStorePersistence:
    def test_set_and_get_result(self, tmp_path, monkeypatch):
        import thrall.tasks.result_store as rs
        monkeypatch.setattr(rs, "_RESULTS_PATH", tmp_path / "task_results.jsonl")
        monkeypatch.setattr(rs, "_results", {})
        monkeypatch.setattr(rs, "_loaded", False)

        task_id = uuid4()
        rs.set_result(task_id, TaskStatus.DONE, "task output", None)

        result = rs.get_result(task_id)
        assert result is not None
        assert result["status"] == "done"
        assert result["result"] == "task output"

    def test_results_persisted_to_disk(self, tmp_path, monkeypatch):
        import thrall.tasks.result_store as rs
        path = tmp_path / "task_results.jsonl"
        monkeypatch.setattr(rs, "_RESULTS_PATH", path)
        monkeypatch.setattr(rs, "_results", {})
        monkeypatch.setattr(rs, "_loaded", False)

        task_id = uuid4()
        rs.set_result(task_id, TaskStatus.DONE, "persisted output", None)

        assert path.exists()
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["task_id"] == str(task_id)

    def test_results_survive_reload(self, tmp_path, monkeypatch):
        import thrall.tasks.result_store as rs
        path = tmp_path / "task_results.jsonl"
        monkeypatch.setattr(rs, "_RESULTS_PATH", path)
        monkeypatch.setattr(rs, "_results", {})
        monkeypatch.setattr(rs, "_loaded", False)

        task_id = uuid4()
        rs.set_result(task_id, TaskStatus.FAILED, None, "something broke")

        # Simulate restart by clearing in-memory store
        monkeypatch.setattr(rs, "_results", {})
        monkeypatch.setattr(rs, "_loaded", False)

        result = rs.get_result(task_id)
        assert result is not None
        assert result["status"] == "failed"
        assert result["error"] == "something broke"


# ── SCHEDULER ATOMIC WRITES ───────────────────────────────────────────────────

class TestSchedulerAtomicWrites:
    def test_atomic_write_no_tmp_left_on_success(self, tmp_path, monkeypatch):
        import scheduler.store as store
        jobs_path = tmp_path / "jobs.json"
        monkeypatch.setattr(store, "_JOBS_PATH", jobs_path)

        store._save_raw([{"id": "job1", "name": "test"}])

        assert jobs_path.exists()
        assert not (tmp_path / "jobs.tmp").exists()

    def test_load_raw_returns_empty_on_corrupted_file(self, tmp_path, monkeypatch):
        import scheduler.store as store
        jobs_path = tmp_path / "jobs.json"
        jobs_path.write_text("this is not valid json {{{{", encoding="utf-8")
        monkeypatch.setattr(store, "_JOBS_PATH", jobs_path)

        result = store._load_raw()
        assert result == []

    def test_roundtrip_save_and_load(self, tmp_path, monkeypatch):
        import scheduler.store as store
        jobs_path = tmp_path / "jobs.json"
        monkeypatch.setattr(store, "_JOBS_PATH", jobs_path)

        store._save_raw([{"id": "abc", "name": "nightly"}])
        loaded = store._load_raw()
        assert loaded == [{"id": "abc", "name": "nightly"}]


# ── PROTECTED PATH RESOLUTION ─────────────────────────────────────────────────

class TestProtectedPaths:
    def test_env_file_is_protected(self):
        assert is_protected(Path(".env")) is True

    def test_env_local_is_protected(self):
        assert is_protected(Path(".env.local")) is True

    def test_env_production_is_protected(self):
        assert is_protected(Path(".env.production")) is True

    def test_pem_file_is_protected(self):
        assert is_protected(Path("server.pem")) is True

    def test_key_file_is_protected(self):
        assert is_protected(Path("private.key")) is True

    def test_regular_python_file_not_protected(self):
        assert is_protected(Path("main.py")) is False

    def test_config_toml_not_protected(self):
        assert is_protected(Path("config.toml")) is False

    def test_filter_protected_removes_env(self):
        paths = [Path("main.py"), Path(".env"), Path("README.md"), Path("server.pem")]
        filtered = filter_protected(paths)
        names = [p.name for p in filtered]
        assert ".env" not in names
        assert "server.pem" not in names
        assert "main.py" in names
        assert "README.md" in names

    def test_filter_protected_empty_list(self):
        assert filter_protected([]) == []
