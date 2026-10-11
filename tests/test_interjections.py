"""Mid-task messages — queued while a task runs, injected into the running loop."""
from __future__ import annotations
from uuid import uuid4
import pytest
from schemas.llm import LLMResponse
from services import interjections
from thrall import coordinator
from constants.coordinator import INTERJECTION_ACK, INTERJECTION_PREFIX, MAX_PENDING_INTERJECTIONS


class FakeLLM:
    """Returns scripted responses; records the messages each call received."""
    def __init__(self, responses, on_call=None):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []
        self.on_call = on_call

    async def __call__(self, messages, tool_defs):
        self.calls.append([dict(m) for m in messages])
        if self.on_call:
            self.on_call(len(self.calls))
        return self.responses.pop(0)


def _user_texts(messages: list[dict]) -> list[str]:
    return [m["content"] for m in messages if m["role"] == "user"]


class TestQueue:
    def test_add_and_drain_in_order(self):
        sid = uuid4()
        interjections.add(sid, "one")
        interjections.add(sid, "two")
        assert interjections.has_pending(sid)
        assert interjections.drain(sid) == ["one", "two"]
        assert not interjections.has_pending(sid)
        assert interjections.drain(sid) == []

    def test_cap_drops_oldest(self):
        sid = uuid4()
        for i in range(MAX_PENDING_INTERJECTIONS + 3):
            interjections.add(sid, str(i))
        pending = interjections.drain(sid)
        assert len(pending) == MAX_PENDING_INTERJECTIONS
        assert pending[0] == "3"


class TestCoordinator:
    @pytest.mark.asyncio
    async def test_receive_queues_instead_of_refusing(self, monkeypatch, telegram_message):
        monkeypatch.setattr(coordinator.state, "has_active_task", lambda key: True)
        reply = await coordinator.receive(telegram_message)
        assert reply == INTERJECTION_ACK
        assert interjections.drain(telegram_message.session_id) == ["hello thrall"]

    @pytest.mark.asyncio
    async def test_pending_message_injected_before_next_llm_call(self, monkeypatch, telegram_message):
        fake = FakeLLM([LLMResponse(content="ok")])
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake)
        interjections.add(telegram_message.session_id, "use blue not red")
        reply = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert reply == "ok"
        assert f"{INTERJECTION_PREFIX}\nuse blue not red" in _user_texts(fake.calls[0])

    @pytest.mark.asyncio
    async def test_message_arriving_during_final_reply_is_not_dropped(self, monkeypatch, telegram_message):
        sid = telegram_message.session_id
        fake = FakeLLM(
            [LLMResponse(content="all done"), LLMResponse(content="updated for your note")],
            on_call=lambda n: interjections.add(sid, "actually make it 3 slides") if n == 1 else None,
        )
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake)
        reply = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert reply == "updated for your note"
        assert len(fake.calls) == 2
        assert f"{INTERJECTION_PREFIX}\nactually make it 3 slides" in _user_texts(fake.calls[1])
        assert not interjections.has_pending(sid)
