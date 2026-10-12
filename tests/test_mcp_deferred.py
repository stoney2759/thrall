"""Deferred MCP tool loading — MCP tools hidden until mcp_search loads them per session."""
from __future__ import annotations
import pytest
from uuid import uuid4
from schemas.tool import ToolCall
from services import session_memory
from thrall.tools import registry
from thrall.tools.mcp import search as mcp_search
from hooks import tool_gate
from constants.tools import PROVIDER_TOOL_LIMIT, MCP_SESSION_TOOL_CAP, MCP_SEARCH_MAX_RESULTS, MCP_IDLE_TURNS


def _mcp_def(name: str, description: str) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description, "parameters": {"type": "object", "properties": {}}}}


@pytest.fixture(autouse=True)
def fake_mcp_tools():
    saved = dict(registry._MCP_TOOLS)
    registry._MCP_TOOLS.clear()
    registry.register_mcp_tools([
        _mcp_def("deckcraft__new_presentation", "Create a new presentation"),
        _mcp_def("deckcraft__save_presentation", "Save the presentation to a path"),
        _mcp_def("deckcraft__add_slide", "Add a slide"),
        _mcp_def("photocraft__doc_open", "Open an image or document file"),
        _mcp_def("photocraft__doc_save", "Save the document"),
        _mcp_def("gridcraft__write_cells", "Write values into spreadsheet cells"),
    ])
    yield
    registry._MCP_TOOLS.clear()
    registry._MCP_TOOLS.update(saved)


def _names(defs: list[dict]) -> set[str]:
    return {d["function"]["name"] for d in defs}


def _search_call(session_id, query: str) -> ToolCall:
    return ToolCall(session_id=session_id, name=mcp_search.NAME, args={"query": query}, caller="thrall")


class TestDeferredLoading:
    def test_mcp_tools_hidden_until_loaded(self):
        names = _names(registry.get_definitions(loaded_mcp=[]))
        assert mcp_search.NAME in names
        assert not any("__" in n for n in names)

    def test_search_loads_tools_into_session(self):
        sid = uuid4()
        result = mcp_search.execute(_search_call(sid, "deckcraft new save"))
        assert result.error is None
        loaded = session_memory.get_loaded_mcp_tools(sid)
        assert "deckcraft__new_presentation" in loaded
        assert "deckcraft__save_presentation" in loaded
        names = _names(registry.get_definitions(loaded_mcp=loaded))
        assert "deckcraft__new_presentation" in names
        assert "photocraft__doc_open" not in names

    def test_loaded_tools_are_per_session(self):
        a, b = uuid4(), uuid4()
        mcp_search.execute(_search_call(a, "photocraft open"))
        assert "photocraft__doc_open" in session_memory.get_loaded_mcp_tools(a)
        assert session_memory.get_loaded_mcp_tools(b) == []

    def test_select_exact_names(self):
        sid = uuid4()
        mcp_search.execute(_search_call(sid, "select:gridcraft__write_cells, nope__missing"))
        assert session_memory.get_loaded_mcp_tools(sid) == ["gridcraft__write_cells"]

    def test_no_match_lists_servers(self):
        result = mcp_search.execute(_search_call(uuid4(), "zzzz"))
        assert "No MCP tools matched" in result.output
        assert "deckcraft" in result.output

    def test_empty_query_errors(self):
        assert mcp_search.execute(_search_call(uuid4(), "  ")).error

    def test_search_result_cap(self):
        registry.register_mcp_tools([_mcp_def(f"bulk__tool_{i}", "bulk tool") for i in range(50)])
        assert len(registry.search_mcp("bulk", MCP_SEARCH_MAX_RESULTS)) == MCP_SEARCH_MAX_RESULTS

    def test_server_name_does_not_match_inside_tool_names(self):
        """'rea' is a server, so it must not also match every tool named 'read_...' on other servers."""
        registry.register_mcp_tools([
            _mcp_def("rea__binary_overview", "Summarise a native binary"),
            _mcp_def("rea__read_bytes", "Read raw bytes"),
            _mcp_def("github__read_file", "Read a file from a repository"),
        ])
        found = registry.search_mcp("rea binary", MCP_SEARCH_MAX_RESULTS)
        assert found[0] == "rea__binary_overview"
        assert "github__read_file" not in found

    def test_server_only_query_gives_overview_and_loads_nothing(self):
        registry.register_mcp_tools([_mcp_def(f"rea__read_{i}", "Read something") for i in range(20)])
        sid = uuid4()
        result = mcp_search.execute(_search_call(sid, "rea"))
        assert "Nothing loaded" in result.output
        assert "rea: 20 tools" in result.output
        assert session_memory.get_loaded_mcp_tools(sid) == []

    def test_session_cap_drops_oldest(self):
        sid = uuid4()
        names = [f"bulk__tool_{i}" for i in range(MCP_SESSION_TOOL_CAP + 5)]
        session_memory.load_mcp_tools(sid, names, MCP_SESSION_TOOL_CAP)
        loaded = session_memory.get_loaded_mcp_tools(sid)
        assert len(loaded) == MCP_SESSION_TOOL_CAP
        assert loaded[0] == "bulk__tool_5"

    def test_cap_drops_least_recently_used_not_oldest_loaded(self):
        sid = uuid4()
        session_memory.load_mcp_tools(sid, ["a__1", "a__2", "a__3"], 3)
        session_memory.touch_mcp_tool(sid, "a__1")            # a__1 used → most recent
        session_memory.load_mcp_tools(sid, ["a__4"], 3)       # over cap → drop LRU (a__2)
        assert session_memory.get_loaded_mcp_tools(sid) == ["a__3", "a__1", "a__4"]

    def test_idle_tools_unload_after_idle_turns(self):
        sid = uuid4()
        session_memory.begin_user_turn(sid, MCP_IDLE_TURNS)
        session_memory.load_mcp_tools(sid, ["a__idle", "a__busy"], MCP_SESSION_TOOL_CAP)
        for _ in range(MCP_IDLE_TURNS):
            session_memory.begin_user_turn(sid, MCP_IDLE_TURNS)
            session_memory.touch_mcp_tool(sid, "a__busy")
        assert "a__idle" in session_memory.get_loaded_mcp_tools(sid)   # exactly at the limit: kept
        unloaded = session_memory.begin_user_turn(sid, MCP_IDLE_TURNS)
        assert unloaded == ["a__idle"]
        assert session_memory.get_loaded_mcp_tools(sid) == ["a__busy"]

    def test_touch_ignores_tools_not_loaded(self):
        sid = uuid4()
        session_memory.touch_mcp_tool(sid, "filesystem_read")
        assert session_memory.get_loaded_mcp_tools(sid) == []

    def test_reload_after_unload(self):
        sid = uuid4()
        mcp_search.execute(_search_call(sid, "select:gridcraft__write_cells"))
        for _ in range(MCP_IDLE_TURNS + 1):
            session_memory.begin_user_turn(sid, MCP_IDLE_TURNS)
        assert session_memory.get_loaded_mcp_tools(sid) == []
        mcp_search.execute(_search_call(sid, "select:gridcraft__write_cells"))
        assert session_memory.get_loaded_mcp_tools(sid) == ["gridcraft__write_cells"]

    def test_catalog_lists_every_server(self):
        catalog = registry.mcp_catalog()
        for server in ("deckcraft", "photocraft", "gridcraft"):
            assert server in catalog


class TestProviderLimit:
    def test_never_exceeds_provider_limit(self):
        many = [f"bulk__tool_{i}" for i in range(700)]
        registry.register_mcp_tools([_mcp_def(n, "bulk") for n in many])
        assert len(registry.get_definitions(loaded_mcp=many)) <= PROVIDER_TOOL_LIMIT
        assert len(registry.get_definitions(allowed=list(registry._SCHEMAS) + many)) <= PROVIDER_TOOL_LIMIT

    def test_full_session_fits_under_limit(self):
        many = [f"bulk__tool_{i}" for i in range(MCP_SESSION_TOOL_CAP)]
        registry.register_mcp_tools([_mcp_def(n, "bulk") for n in many])
        defs = registry.get_definitions(loaded_mcp=many)
        assert len(defs) == len(registry._SCHEMAS) + MCP_SESSION_TOOL_CAP  # nothing truncated


class TestWorkersAndGate:
    def test_worker_allowed_list_unchanged(self):
        names = _names(registry.get_definitions(allowed=["filesystem_read", "deckcraft__add_slide"]))
        assert names == {"filesystem_read", "deckcraft__add_slide"}

    def test_search_never_grants_permission(self):
        """Loading a tool makes it visible; a worker without the profile is still denied."""
        sid = uuid4()
        mcp_search.execute(_search_call(sid, "deckcraft slide"))
        worker_call = ToolCall(session_id=sid, name="deckcraft__add_slide", args={}, caller="agent:abc")
        assert tool_gate.is_allowed(worker_call) is False
