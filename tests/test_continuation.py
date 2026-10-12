"""A named agent's finished work is kept for its next spawn — whatever the transport, silent or not."""
from __future__ import annotations
import pytest
from schemas.task import Task, TaskType, TaskStatus, CapabilityProfile
from thrall.tasks import continuation_store
from thrall.tasks.pool import _save_continuation


def _task(profile: str, status: TaskStatus = TaskStatus.DONE, result: str | None = "found it", silent: bool = True) -> Task:
    return Task(
        type=TaskType.LOCAL, brief="set up rea", status=status, result=result, silent=silent,
        profile=CapabilityProfile(name=profile, allowed_tools=[]),
    )


@pytest.fixture(autouse=True)
def clean_store():
    continuation_store._store.clear()
    yield
    continuation_store._store.clear()


def test_silent_named_agent_is_kept():
    _save_continuation(_task("mcp-setup", silent=True))
    assert continuation_store.pop("mcp-setup") == {"brief": "set up rea", "result": "found it"}


def test_default_profile_is_not_kept():
    _save_continuation(_task("default"))
    assert continuation_store.pop("default") is None


def test_failed_or_empty_agent_is_not_kept():
    _save_continuation(_task("mcp-setup", status=TaskStatus.FAILED))
    _save_continuation(_task("researcher", result=None))
    assert continuation_store.pop("mcp-setup") is None
    assert continuation_store.pop("researcher") is None
