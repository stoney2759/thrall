"""Finished background tasks are handed back to Thrall's reasoning loop."""
from __future__ import annotations
from uuid import uuid4
import pytest
from schemas.message import Transport
from schemas.task import Task, TaskType, TaskStatus, CapabilityProfile
from services import background_wake, interjections
from thrall import coordinator
from constants.agents import BACKGROUND_RESULT_HEADER, BACKGROUND_RESULT_MAX_CHARS


def _task(**kw) -> Task:
    base = dict(type=TaskType.LOCAL, brief="process the video", profile=CapabilityProfile(name="video-processor", allowed_tools=[]),
                status=TaskStatus.DONE, result="report text", session_id=uuid4())
    base.update(kw)
    return Task(**base)


class TestShouldWake:
    def test_wakes_for_finished_task_with_session(self):
        assert background_wake.should_wake(_task())
        assert background_wake.should_wake(_task(status=TaskStatus.FAILED, result=None, error="boom"))

    def test_skips_silent_sessionless_and_cancelled(self):
        assert not background_wake.should_wake(_task(silent=True))       # mid-task delegation: Thrall awaits it itself
        assert not background_wake.should_wake(_task(session_id=None))
        assert not background_wake.should_wake(_task(status=TaskStatus.CANCELLED))


class TestNotice:
    def test_done_notice(self):
        notice = background_wake.build_notice(_task())
        assert notice.startswith(BACKGROUND_RESULT_HEADER)
        assert "status: done" in notice and "report text" in notice and "video-processor" in notice

    def test_failed_notice_and_long_result_cut(self):
        assert "boom" in background_wake.build_notice(_task(status=TaskStatus.FAILED, result=None, error="boom"))
        notice = background_wake.build_notice(_task(result="x" * (BACKGROUND_RESULT_MAX_CHARS + 50)))
        assert "[cut —" in notice


class TestWake:
    @pytest.mark.asyncio
    async def test_returns_thralls_reply(self, monkeypatch):
        seen = {}

        async def fake_receive(message):
            seen["content"] = message.content
            return "The video report is ready: ..."

        monkeypatch.setattr(coordinator, "receive", fake_receive)
        task = _task()
        reply = await background_wake.wake(task, Transport.TELEGRAM, "authorized_user")
        assert reply == "The video report is ready: ..."
        assert "report text" in seen["content"]

    @pytest.mark.asyncio
    async def test_busy_session_queues_result_and_sends_nothing(self, monkeypatch):
        monkeypatch.setattr(coordinator.state, "has_active_task", lambda key: True)
        task = _task()
        reply = await background_wake.wake(task, Transport.TELEGRAM, "authorized_user")
        assert reply is None
        pending = interjections.drain(task.session_id)
        assert len(pending) == 1 and "report text" in pending[0]
