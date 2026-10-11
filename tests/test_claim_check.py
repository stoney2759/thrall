"""Claim check — replies must not name missing files or claim actions no tool performed.

Cases are taken from real mimo replies on 2026-10-11.
"""
from __future__ import annotations
from uuid import uuid4
import pytest
from bootstrap import state
from schemas.llm import LLMResponse, ToolCallRequest
from schemas.tool import ToolResult
from services import session_memory
from thrall import claim_check, coordinator
from constants.claims import UNVERIFIED_PREFIX, ACTION_FOOTER_PREFIX, CLAIM_EVIDENCE_TURNS

FAKE_MD = r"workspace\prompts\chicken-knight-haybale.md"


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


class TestPaths:
    def test_made_up_file_is_flagged(self, tmp_path):
        reply = f"**1. Banana Pro prompt** — saved to `{FAKE_MD}`."
        assert claim_check.missing_paths(reply, "", set(), [tmp_path]) == [FAKE_MD]

    def test_existing_relative_and_absolute_files_pass(self, tmp_path):
        (tmp_path / "out").mkdir()
        real = tmp_path / "out" / "deck.pptx"
        real.write_text("x")
        reply = f"Saved to `out\\deck.pptx` and {real}"
        assert claim_check.missing_paths(reply, "", set(), [tmp_path]) == []

    def test_user_named_path_is_not_flagged(self, tmp_path):
        reply = f"`{FAKE_MD}` doesn't exist — I fabricated that."
        user = f"where did {FAKE_MD} come from?"
        assert claim_check.missing_paths(reply, user, set(), [tmp_path]) == []

    def test_written_this_turn_counts(self, tmp_path):
        written = {claim_check.normalise(str(tmp_path / "gone.txt"))}
        assert claim_check.missing_paths(f"wrote `{tmp_path / 'gone.txt'}`", "", written, [tmp_path]) == []

    def test_urls_and_bare_filenames_ignored(self):
        assert claim_check.extract_paths("see https://x.com/a.png and `badge.svg`") == []


class TestClaims:
    def test_logged_with_no_write_is_flagged(self):
        problems = claim_check.unbacked_claims("I've logged this as a failure pattern so it doesn't happen again.",
                                               ["clipboard_snippets", "filesystem_find", "clipboard_load"])
        assert problems and "logged" in problems[0]

    def test_logged_with_memory_write_passes(self):
        assert claim_check.unbacked_claims("Noted and stored.", ["memory_write"]) == []

    def test_mcp_save_backs_saved_claim(self):
        assert claim_check.unbacked_claims("Saved the deck.", ["deckcraft__save_presentation"]) == []

    def test_passive_and_negated_are_not_claims(self):
        assert claim_check.unbacked_claims("The prompt was saved to the clipboard snippet only.", []) == []
        assert claim_check.unbacked_claims("I never actually wrote it to a markdown file.", []) == []

    def test_shell_backs_any_claim(self):
        assert claim_check.unbacked_claims("I've deleted the temp files and sent the report.", ["shell_run"]) == []


class TestCompletionClaims:
    """The old fabrication guard's job: 'Done/updated…' when nothing changed this turn."""

    def test_done_with_no_tools_is_flagged(self):
        assert claim_check.unbacked_completion("Done — I've updated the config.", [])

    def test_read_search_and_checklist_tools_are_not_work(self):
        tools = ["filesystem_read", "mcp_search", "todo_write", "skill_load", "deckcraft__inspect_slide"]
        assert claim_check.unbacked_completion("All done — the deck is updated.", tools)

    def test_text_only_revision_passes(self):
        assert claim_check.unbacked_completion("Updated — here's the revised prompt with a white backdrop.", []) == []
        assert claim_check.unbacked_completion("Done. Anything else?", []) == []

    def test_named_file_makes_it_checkable(self):
        assert claim_check.unbacked_completion("Fixed the bug in coordinator.py.", [])

    def test_real_change_this_turn_passes(self):
        assert claim_check.unbacked_completion("Done.", ["filesystem_edit"]) == []
        assert claim_check.unbacked_completion("Fixed it.", ["vectorcraft__draw_shape"]) == []

    def test_ordinary_sentences_pass(self):
        assert claim_check.unbacked_completion("Is the deck finished? It's done when you say so.", []) == []
        assert claim_check.unbacked_completion("I made a mistake there.", []) == []


class TestActionRecord:
    def test_old_turns_drop_out(self):
        sid = uuid4()
        session_memory.record_action(sid, "memory_write", "", CLAIM_EVIDENCE_TURNS)
        for _ in range(CLAIM_EVIDENCE_TURNS):
            session_memory.begin_user_turn(sid, 99)
        assert session_memory.recent_actions(sid, CLAIM_EVIDENCE_TURNS) == []


class TestInLoop:
    @pytest.mark.asyncio
    async def test_false_logged_claim_retried_then_warned(self, monkeypatch, telegram_message):
        fake = FakeLLM([
            LLMResponse(content="I've logged this as a failure pattern."),
            LLMResponse(content="I've logged this as a failure pattern, promise."),
        ])
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake)
        reply = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert len(fake.calls) == 2
        assert UNVERIFIED_PREFIX in reply and "logged" in reply

    @pytest.mark.asyncio
    async def test_honest_fix_after_retry_has_no_warning(self, monkeypatch, telegram_message):
        fake = FakeLLM([
            LLMResponse(content="I've logged this as a failure pattern."),
            _call("memory_write", content="lesson", layer="semantic"),
            LLMResponse(content="I've logged it now."),
        ])
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", fake)
        monkeypatch.setattr(coordinator.tools, "execute", _ok_tool)
        reply = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert reply == "I've logged it now."

    @pytest.mark.asyncio
    async def test_footer_only_when_enabled(self, monkeypatch, telegram_message, tmp_path):
        target = tmp_path / "deck.pptx"
        target.write_bytes(b"x" * 2048)
        script = [_call("deckcraft__save_presentation", path=str(target)), _call("filesystem_stat", path=str(target)),
                  LLMResponse(content="Deck ready.")]
        monkeypatch.setattr(coordinator.tools, "execute", _ok_tool)

        monkeypatch.setattr(coordinator.llm, "complete_with_tools", FakeLLM(list(script)))
        plain = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert plain == "Deck ready."

        state.set_config({**state.get_config(), "harness": {"action_footer": True}})
        session_memory.begin_user_turn(telegram_message.session_id, 99)
        monkeypatch.setattr(coordinator.llm, "complete_with_tools", FakeLLM(list(script)))
        footed = await coordinator._reason([{"role": "system", "content": "sys"}], [], telegram_message)
        assert ACTION_FOOTER_PREFIX in footed and "deck.pptx (2 KB)" in footed
