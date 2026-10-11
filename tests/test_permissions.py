"""Permission modes, rules, and asking the user before Thrall changes anything."""
from __future__ import annotations
import asyncio
from uuid import uuid4
import pytest
from bootstrap import state
from schemas.llm import LLMResponse, ToolCallRequest
from schemas.message import Message, Role, Transport
from schemas.tool import ToolResult
from services import permissions, ask_user_channel
from thrall import coordinator
from commands.base import CommandContext
from commands.permissions import PermissionsCommand
from constants.permissions import (
    MODE_ASK, MODE_TRUSTED, MODE_READ_ONLY, RISK_READ, RISK_CHANGE, RISK_DANGEROUS,
    DECISION_ALLOW, DECISION_DENY, DECISION_ASK,
)


class TestClassify:
    @pytest.mark.parametrize("tool,risk", [
        ("filesystem_read", RISK_READ), ("gridcraft__read_range", RISK_READ), ("mcp_search", RISK_READ),
        ("vectorcraft__open_file", RISK_READ), ("todo_write", RISK_READ),
        ("filesystem_write", RISK_CHANGE), ("deckcraft__add_slide", RISK_CHANGE), ("browser_navigate", RISK_CHANGE),
        ("gridcraft__run_command", RISK_CHANGE),
        ("shell_run", RISK_DANGEROUS), ("powershell_run", RISK_DANGEROUS), ("deckcraft__delete_slide", RISK_DANGEROUS),
        ("tiktok_publish", RISK_DANGEROUS),
    ])
    def test_risk(self, tool, risk):
        assert permissions.classify(tool) == risk


class TestRules:
    def test_tool_and_arg_globs(self):
        assert permissions.rule_matches("deckcraft__*", "deckcraft__add_slide", {})
        assert permissions.rule_matches("shell_run:git status*", "shell_run", {"command": "git status -s"})
        assert not permissions.rule_matches("shell_run:git status*", "shell_run", {"command": "git push"})

    def test_relative_path_pattern_matches_absolute_path(self):
        args = {"path": r"C:\Users\alex\Projects\Thrall\workspace\notes\a.md"}
        assert permissions.rule_matches("filesystem_write:workspace/**", "filesystem_write", args)
        assert not permissions.rule_matches("filesystem_write:workspace/**", "filesystem_write", {"path": r"C:\Windows\a.md"})

    def test_deny_beats_allow_and_trusted(self):
        args = {"command": "Remove-Item -Recurse C:\\x"}
        decision, _ = permissions.decide("powershell_run", args, MODE_TRUSTED,
                                         ["powershell_run"], ["powershell_run:*remove-item*"], [])
        assert decision == DECISION_DENY


class TestModes:
    def test_ask_mode(self):
        assert permissions.decide("filesystem_read", {}, MODE_ASK, [], [], [])[0] == DECISION_ALLOW
        assert permissions.decide("memory_write", {}, MODE_ASK, [], [], [])[0] == DECISION_ALLOW
        assert permissions.decide("filesystem_write", {}, MODE_ASK, [], [], [])[0] == DECISION_ASK
        assert permissions.decide("deckcraft__add_slide", {}, MODE_ASK, [], [], ["deckcraft__*"])[0] == DECISION_ALLOW

    def test_trusted_and_read_only(self):
        assert permissions.decide("shell_run", {}, MODE_TRUSTED, [], [], [])[0] == DECISION_ALLOW
        assert permissions.decide("filesystem_write", {}, MODE_READ_ONLY, [], [], [])[0] == DECISION_DENY
        assert permissions.decide("filesystem_read", {}, MODE_READ_ONLY, [], [], [])[0] == DECISION_ALLOW

    def test_unknown_mode_falls_back_to_ask(self):
        assert permissions.current_mode({"permissions": {"mode": "yolo"}}, None) == MODE_ASK
        assert permissions.current_mode({"permissions": {"mode": MODE_TRUSTED}}, MODE_READ_ONLY) == MODE_READ_ONLY

    def test_answers_and_always_scope(self):
        assert permissions.parse_answer("Yes!") == "yes"
        assert permissions.parse_answer("always") == "always"
        assert permissions.parse_answer("[Timeout: user did not reply within 300s]") == "no"
        assert permissions.always_scope("deckcraft__add_slide") == "deckcraft__*"
        assert permissions.always_scope("shell_run") == "shell_run"


def _message(transport=Transport.TELEGRAM) -> Message:
    return Message(session_id=uuid4(), role=Role.USER, content="do it", transport=transport, user_id="authorized_user")


async def _answer_when_asked(sid, answer: str, asked: list[str]) -> None:
    for _ in range(200):
        if ask_user_channel.has_pending(sid):
            ask_user_channel.deliver_reply(sid, answer)
            return
        await asyncio.sleep(0.01)


class TestAskFlow:
    @pytest.fixture(autouse=True)
    def ask_mode(self):
        state.set_config({**state.get_config(), "permissions": {"mode": MODE_ASK}})

    @pytest.mark.asyncio
    async def test_yes_runs_no_denies(self):
        for answer, expect_denied in (("yes", False), ("no", True)):
            msg = _message()
            asked: list[str] = []

            async def sender(text, asked=asked):
                asked.append(text)
            ask_user_channel.register_sender(msg.session_id, sender)
            result, _ = await asyncio.gather(
                coordinator._check_permission(msg, "filesystem_write", {"path": "a.txt"}),
                _answer_when_asked(msg.session_id, answer, asked),
            )
            assert (result is not None) == expect_denied
            assert asked and "filesystem_write" in asked[0] and "a.txt" in asked[0]
            if expect_denied:  # must read as the user's choice and forbid workarounds (live bug 2026-10-11)
                assert "USER DECLINED" in result and "another way" in result

    @pytest.mark.asyncio
    async def test_always_covers_the_whole_mcp_server(self):
        msg = _message()

        async def sender(text):
            pass
        ask_user_channel.register_sender(msg.session_id, sender)
        first, _ = await asyncio.gather(
            coordinator._check_permission(msg, "deckcraft__add_slide", {}),
            _answer_when_asked(msg.session_id, "always", []),
        )
        assert first is None
        assert await coordinator._check_permission(msg, "deckcraft__save_presentation", {"path": "x.pptx"}) is None

    @pytest.mark.asyncio
    async def test_unattended_runs_are_denied_not_hung(self):
        assert "nobody is attached" in await coordinator._check_permission(_message(), "filesystem_write", {})
        scheduled = _message(Transport.SCHEDULER)
        ask_user_channel.register_sender(scheduled.session_id, lambda t: None)
        assert "nobody is attached" in await coordinator._check_permission(scheduled, "filesystem_write", {})

    @pytest.mark.asyncio
    async def test_denied_tool_is_not_executed(self, monkeypatch, telegram_message):
        state.set_config({**state.get_config(), "permissions": {"mode": MODE_READ_ONLY}})
        executed: list[str] = []

        async def tool(name, args, session_id, caller):
            executed.append(name)
            return ToolResult(call_id=uuid4(), output="ok", duration_ms=1)

        script = [LLMResponse(content=None, finish_reason="tool_calls", tool_calls=[
            ToolCallRequest(id="1", name="filesystem_write", args={"path": "a.txt", "content": "x"})]),
            LLMResponse(content="I couldn't write it — read-only mode.")]

        async def fake_llm(messages, tool_defs):
            return script.pop(0)
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake_llm)
        monkeypatch.setattr(coordinator.tools, "execute", tool)
        reply = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert executed == [] and "read-only" in reply


class TestButtonsAndOutcome:
    def test_outcome_lines(self):
        assert permissions.outcome_text("shell_run", "yes", "yes") == "🔐 shell_run — ✅ allowed once"
        assert "deckcraft (all tools) — ♾ allowed for this session" in permissions.outcome_text(
            "deckcraft__add_slide", "always", "always")
        assert "❌ declined" in permissions.outcome_text("code_execute", "no", "no")
        assert "⌛ no answer" in permissions.outcome_text("code_execute", "no", "[Timeout: user did not reply within 300s]")

    @pytest.mark.asyncio
    async def test_buttons_shown_then_question_replaced_by_outcome(self):
        state.set_config({**state.get_config(), "permissions": {"mode": MODE_ASK}})
        msg = _message()
        shown: list[tuple[str, list[str]]] = []
        resolved: list[str] = []
        typed: list[str] = []

        async def plain(text):
            typed.append(text)

        async def show(question, choices):
            shown.append((question, choices))

        async def resolve(outcome):
            resolved.append(outcome)
        ask_user_channel.register_sender(msg.session_id, plain)
        ask_user_channel.register_choice_ui(msg.session_id, show, resolve)
        result, _ = await asyncio.gather(
            coordinator._check_permission(msg, "deckcraft__add_slide", {}),
            _answer_when_asked(msg.session_id, "always", []),  # a button tap delivers the value
        )
        assert result is None
        assert shown and shown[0][1] == ["yes", "always", "no"] and typed == []
        assert resolved == ["🔐 deckcraft (all tools) — ♾ allowed for this session"]

    @pytest.mark.asyncio
    async def test_transports_without_buttons_get_plain_question(self):
        sid = uuid4()
        typed: list[str] = []

        async def plain(text):
            typed.append(text)
        ask_user_channel.register_sender(sid, plain)
        reply, _ = await asyncio.gather(
            ask_user_channel.ask(sid, "ok?", timeout_seconds=2, choices=["yes", "no"]),
            _answer_when_asked(sid, "yes", []),
        )
        assert reply == "yes" and typed == ["ok?"]
        await ask_user_channel.resolve(sid, "done")  # no resolver registered — must not fail


class TestCommand:
    @pytest.mark.asyncio
    async def test_set_show_and_reset(self):
        cmd = PermissionsCommand()
        sid = uuid4()
        ctx = lambda *a: CommandContext(user_id="u", session_id=sid, transport=Transport.CLI, args=list(a))
        assert "read_only" in await cmd.execute(ctx("read_only"))
        assert state.get_permission_mode_override() == MODE_READ_ONLY
        assert "Unknown mode" in await cmd.execute(ctx("yolo"))
        await cmd.execute(ctx("reset"))
        assert state.get_permission_mode_override() is None
