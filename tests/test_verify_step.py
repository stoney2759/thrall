"""In-task checklist (todo_write) and the harness verify step before a final reply."""
from __future__ import annotations
from uuid import uuid4
import pytest
from schemas.llm import LLMResponse, ToolCallRequest
from schemas.memory import TodoStatus
from schemas.tool import ToolCall, ToolResult
from services import session_memory
from thrall import coordinator
from thrall.tools.todo import write as todo_write
from constants.tools import TODO_MAX_ITEMS
from constants.claims import UNVERIFIED_PREFIX

PATH = r"C:\tmp\eggs.xlsx"
_REAL_PATH_EXISTS = coordinator._path_exists


@pytest.fixture(autouse=True)
def written_files_exist(monkeypatch):
    """PATH is never really written in these tests — treat it as present unless a test says otherwise."""
    monkeypatch.setattr(coordinator, "_path_exists", lambda path: True)


def _todo_call(sid, items) -> ToolCall:
    return ToolCall(session_id=sid, name=todo_write.NAME, args={"items": items}, caller="thrall")


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    async def __call__(self, messages, tool_defs):
        self.calls.append([dict(m) for m in messages])
        return self.responses.pop(0)


async def _ok_tool(name, args, session_id, caller):
    return ToolResult(call_id=uuid4(), output="ok", duration_ms=1)


def _call(name: str, **args) -> LLMResponse:
    return LLMResponse(content=None, tool_calls=[ToolCallRequest(id=str(uuid4()), name=name, args=args)],
                       finish_reason="tool_calls")


def _harness_checks(calls: list[list[dict]]) -> list[str]:
    """Checks present in the final request's history (each one persists in later calls)."""
    return [m["content"] for m in calls[-1]
            if m["role"] == "system" and m["content"].startswith("HARNESS CHECK")]


class TestTodoWrite:
    def test_replaces_list_and_renders(self):
        sid = uuid4()
        result = todo_write.execute(_todo_call(sid, [
            {"content": "draw circle", "status": "done"},
            {"content": "add text", "status": "in_progress"},
        ]))
        assert result.error is None
        assert "1/2 done" in result.output and "[x] draw circle" in result.output and "[~] add text" in result.output
        todo_write.execute(_todo_call(sid, [{"content": "export", "status": "pending"}]))
        assert [t.content for t in session_memory.get_todos(sid)] == ["export"]

    def test_rejects_bad_input(self):
        sid = uuid4()
        assert todo_write.execute(_todo_call(sid, [])).error
        assert todo_write.execute(_todo_call(sid, [{"content": " ", "status": "done"}])).error
        assert todo_write.execute(_todo_call(sid, [{"content": "x", "status": "finished"}])).error
        too_many = [{"content": str(i), "status": "pending"} for i in range(TODO_MAX_ITEMS + 1)]
        assert todo_write.execute(_todo_call(sid, too_many)).error


class TestVerifyProblems:
    def test_write_then_read_same_path_is_fine(self):
        w, r, s = {}, {}, {}
        coordinator._track_file_access("filesystem_write", {"path": PATH}, 0, w, r, s)
        coordinator._track_file_access("filesystem_cat", {"path": PATH}, 1, w, r, s)
        assert coordinator._verify_problems(uuid4(), set(), w, r, s) == []

    def test_write_without_read_is_flagged(self):
        w, r, s = {}, {}, {}
        coordinator._track_file_access("gridcraft__save_workbook", {"path": PATH}, 0, w, r, s)
        problems = coordinator._verify_problems(uuid4(), set(), w, r, s)
        assert problems and "not re-read" in problems[0]

    def test_read_in_same_batch_does_not_count(self):
        w, r, s = {}, {}, {}
        coordinator._track_file_access("filesystem_write", {"path": PATH}, 2, w, r, s)
        coordinator._track_file_access("filesystem_stat", {"path": PATH}, 2, w, r, s)
        assert coordinator._verify_problems(uuid4(), set(), w, r, s)

    def test_same_mcp_app_inspection_counts_other_app_does_not(self):
        w, r, s = {}, {}, {}
        coordinator._track_file_access("gridcraft__save_workbook", {"path": PATH}, 0, w, r, s)
        coordinator._track_file_access("deckcraft__inspect_document", {}, 1, w, r, s)
        assert coordinator._verify_problems(uuid4(), set(), w, r, s)
        coordinator._track_file_access("gridcraft__read_range", {"range": "A1:B9"}, 2, w, r, s)
        assert coordinator._verify_problems(uuid4(), set(), w, r, s) == []

    def test_written_then_deleted_is_not_flagged(self, monkeypatch, tmp_path):
        """A test folder written and cleaned up in the same turn has nothing left to re-read."""
        from bootstrap import state
        monkeypatch.setattr(coordinator, "_path_exists", _REAL_PATH_EXISTS)
        monkeypatch.setattr(state, "get_workspace_dir", lambda: str(tmp_path))
        (tmp_path / "kept.txt").write_text("x")
        w, r, s = {}, {}, {}
        coordinator._track_file_access("filesystem_write", {"path": "kept.txt"}, 0, w, r, s)
        coordinator._track_file_access("filesystem_write", {"path": "gone.txt"}, 0, w, r, s)
        problems = coordinator._verify_problems(uuid4(), set(), w, r, s)
        assert problems and "kept.txt" in problems[0] and "gone.txt" not in problems[0]

    def test_unfinished_checklist_only_flagged_when_used_this_turn(self):
        sid = uuid4()
        todo_write.execute(_todo_call(sid, [{"content": "export pdf", "status": "pending"}]))
        assert coordinator._verify_problems(sid, set(), {}, {}, {}) == []
        problems = coordinator._verify_problems(sid, {todo_write.NAME}, {}, {}, {})
        assert problems and "export pdf" in problems[0]


class TestVerifyInLoop:
    @pytest.mark.asyncio
    async def test_unverified_write_sends_reply_back_once(self, monkeypatch, telegram_message):
        fake = FakeLLM([
            _call("filesystem_write", path=PATH, content="x"),
            LLMResponse(content="Saved it."),
            _call("filesystem_cat", path=PATH),
            LLMResponse(content="Saved and checked: 1 line."),
        ])
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake)
        monkeypatch.setattr(coordinator.tools, "execute", _ok_tool)
        reply = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert reply == "Saved and checked: 1 line."
        assert len(_harness_checks(fake.calls)) == 1

    @pytest.mark.asyncio
    async def test_still_failing_after_retry_is_sent_with_warning(self, monkeypatch, telegram_message):
        fake = FakeLLM([
            _call("filesystem_write", path=PATH, content="x"),
            LLMResponse(content="Saved it."),
            LLMResponse(content="Saved it, honestly."),
        ])
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake)
        monkeypatch.setattr(coordinator.tools, "execute", _ok_tool)
        reply = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert reply.startswith("Saved it, honestly.")
        assert UNVERIFIED_PREFIX in reply and "not re-read" in reply
        assert len(fake.calls) == 3  # one retry only

    @pytest.mark.asyncio
    async def test_plain_chat_reply_is_untouched(self, monkeypatch, telegram_message):
        fake = FakeLLM([LLMResponse(content="Hi Jay")])
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake)
        assert await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message) == "Hi Jay"
        assert len(fake.calls) == 1
