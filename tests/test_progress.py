"""Live progress — step labels and the throttled, edited-in-place status message."""
from __future__ import annotations
import asyncio
from uuid import uuid4
import pytest
from services import progress
from constants.progress import PROGRESS_VISIBLE_STEPS


class TestLabel:
    def test_mcp_and_native_labels_show_file_name_only(self):
        assert progress.label("deckcraft__add_slide", {}) == "deckcraft: add slide"
        assert progress.label("filesystem_write", {"path": r"C:\Users\alex\secret\ideas.txt", "content": "x"}) == "writing ideas.txt"
        assert progress.label("shell_run", {"command": "echo $TOKEN"}) == "running a command"


class FakeChat:
    def __init__(self):
        self.sent: list[str] = []
        self.edits: list[str] = []
        self.deleted = False

    async def send(self, text):
        self.sent.append(text)
        return "msg-1"

    async def edit(self, handle, text):
        self.edits.append(text)

    async def delete(self, handle):
        self.deleted = True


class TestStatusBoard:
    @pytest.mark.asyncio
    async def test_first_step_sends_then_edits_are_throttled(self):
        chat = FakeChat()
        board = progress.StatusBoard(chat.send, chat.edit, chat.delete, min_interval=0.05)
        await board.add("loading tools")
        await board.add("deckcraft: add slide")
        await board.add("deckcraft: save presentation")
        assert len(chat.sent) == 1 and chat.edits == []          # burst collapsed into one pending edit
        await asyncio.sleep(0.1)
        assert len(chat.edits) == 1 and "save presentation" in chat.edits[0]
        await board.close()
        assert chat.deleted

    @pytest.mark.asyncio
    async def test_repeats_skipped_and_only_recent_steps_shown(self):
        chat = FakeChat()
        board = progress.StatusBoard(chat.send, chat.edit, chat.delete, min_interval=0)
        for i in range(PROGRESS_VISIBLE_STEPS + 3):
            await board.add(f"step {i}")
            await board.add(f"step {i}")
        text = board.render()
        assert "step 0" not in text and f"step {PROGRESS_VISIBLE_STEPS + 2}" in text
        assert f"({PROGRESS_VISIBLE_STEPS + 3} steps)" in text

    @pytest.mark.asyncio
    async def test_parallel_steps_make_one_message_not_two(self):
        """Live bug 2026-10-11: skill_load + mcp_search in parallel sent two 'Working…' messages."""
        chat = FakeChat()

        async def slow_send(text):
            await asyncio.sleep(0.02)  # network latency — second step arrives mid-send
            return await chat.send(text)

        board = progress.StatusBoard(slow_send, chat.edit, chat.delete, min_interval=0.03)
        await asyncio.gather(board.add("loading skill pptx"), board.add("loading tools"))
        await asyncio.sleep(0.1)
        assert len(chat.sent) == 1
        assert "loading tools" in (chat.edits[-1] if chat.edits else chat.sent[0])
        await board.close()
        assert chat.deleted

    @pytest.mark.asyncio
    async def test_no_status_message_if_no_steps(self):
        chat = FakeChat()
        board = progress.StatusBoard(chat.send, chat.edit, chat.delete)
        await board.close()
        assert chat.sent == [] and not chat.deleted


class TestEmit:
    @pytest.mark.asyncio
    async def test_listener_errors_never_break_the_task(self):
        sid = uuid4()

        async def broken(text):
            raise RuntimeError("telegram down")
        progress.register(sid, broken)
        await progress.emit(sid, "writing a.txt")  # must not raise
        progress.unregister(sid, broken)
        await progress.emit(sid, "nobody listening")
