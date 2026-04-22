from __future__ import annotations
import pytest
import pytest_asyncio
from uuid import uuid4
from schemas.memory import Episode, KnowledgeFact
from services.memory.backends.session import SessionBackend


@pytest_asyncio.fixture
async def backend():
    b = SessionBackend()
    await b.connect()
    return b


class TestSessionBackendLifecycle:
    @pytest.mark.asyncio
    async def test_not_ready_before_connect(self):
        b = SessionBackend()
        assert b.is_ready() is False

    @pytest.mark.asyncio
    async def test_ready_after_connect(self, backend):
        assert backend.is_ready() is True

    @pytest.mark.asyncio
    async def test_not_ready_after_disconnect(self, backend):
        await backend.disconnect()
        assert backend.is_ready() is False

    def test_name(self, ):
        b = SessionBackend()
        assert b.name() == "session"


class TestSessionBackendEpisodes:
    @pytest.mark.asyncio
    async def test_write_and_get_episode(self, backend):
        sid = uuid4()
        ep = Episode(session_id=sid, role="user", content="Test episode content here.")
        await backend.write_episode(ep)
        results = await backend.get_episodes(sid, limit=10)
        assert len(results) == 1
        assert results[0].content == "Test episode content here."

    @pytest.mark.asyncio
    async def test_get_episodes_limit(self, backend):
        sid = uuid4()
        for i in range(5):
            await backend.write_episode(Episode(session_id=sid, role="user",
                                                content=f"Episode {i}"))
        results = await backend.get_episodes(sid, limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_episodes_filters_by_session(self, backend):
        sid_a, sid_b = uuid4(), uuid4()
        await backend.write_episode(Episode(session_id=sid_a, role="user",
                                            content="Session A content"))
        await backend.write_episode(Episode(session_id=sid_b, role="user",
                                            content="Session B content"))
        results = await backend.get_episodes(sid_a, limit=10)
        assert len(results) == 1
        assert "Session A" in results[0].content

    @pytest.mark.asyncio
    async def test_search_episodes_by_keyword(self, backend):
        sid = uuid4()
        await backend.write_episode(Episode(session_id=sid, role="user",
                                            content="The deployment pipeline is broken"))
        await backend.write_episode(Episode(session_id=sid, role="user",
                                            content="Weather looks nice today"))
        results = await backend.search_episodes("deployment", limit=10)
        assert len(results) == 1
        assert "deployment" in results[0].content


class TestSessionBackendFacts:
    @pytest.mark.asyncio
    async def test_write_and_search_fact(self, backend):
        fact = KnowledgeFact(content="Thrall uses OpenRouter as primary LLM provider",
                             source="test", confidence=0.9)
        await backend.write_fact(fact)
        results = await backend.search_facts("OpenRouter", limit=10)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_facts_no_match(self, backend):
        results = await backend.search_facts("nonexistent_query_xyz", limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_delete_fact(self, backend):
        fact = KnowledgeFact(content="Fact to delete later.", source="test")
        await backend.write_fact(fact)
        await backend.delete_fact(fact.id)
        results = await backend.search_facts("delete", limit=10)
        assert results == []
