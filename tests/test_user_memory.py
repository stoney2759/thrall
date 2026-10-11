"""Always-loaded user memory — facts the user gave Thrall reach context every turn."""
from __future__ import annotations
import pytest
from schemas.memory import KnowledgeFact
from services.memory.backends.session import SessionBackend
from hooks import context_gate
from thrall.context import select_user_facts
from constants.memory import USER_FACTS_MAX, USER_FACTS_MAX_CHARS


def _fact(content: str, source: str) -> KnowledgeFact:
    return KnowledgeFact(content=content, source=source)


class TestSelectUserFacts:
    def test_only_user_sourced_facts(self):
        facts = [_fact("tell me about workarounds", "user-feedback"), _fact("API is up", "thrall"),
                 _fact("dad is Robert", "User statement on 2026-05-06")]
        assert [f.content for f in select_user_facts(facts)] == ["tell me about workarounds", "dad is Robert"]

    def test_count_cap_keeps_newest(self):
        facts = [_fact(f"pref {i}", "user") for i in range(USER_FACTS_MAX + 5)]
        kept = select_user_facts(facts)
        assert len(kept) == USER_FACTS_MAX and kept[-1].content == f"pref {USER_FACTS_MAX + 4}"

    def test_char_cap_drops_oldest(self):
        big = "x" * (USER_FACTS_MAX_CHARS // 2)
        kept = select_user_facts([_fact("old " + big, "user"), _fact("mid " + big, "user"), _fact("new", "user")])
        assert [f.content[:3] for f in kept] == ["mid", "new"]


class TestBackendAndContext:
    @pytest.mark.asyncio
    async def test_session_backend_lists_facts(self):
        backend = SessionBackend()
        await backend.connect()
        for i in range(3):
            await backend.write_fact(_fact(f"f{i}", "user"))
        assert [f.content for f in await backend.list_facts(2)] == ["f1", "f2"]

    def test_block_present_without_keyword_match(self):
        msgs = context_gate.build_context(session_context=[], episodes=[], facts=[],
                                          user_facts=[_fact("Always disclose workarounds", "user-feedback")])
        block = [m["content"] for m in msgs if m["content"].startswith("## What the user has told me")]
        assert block and "Always disclose workarounds" in block[0]
