"""Fixes from the 2026-10-12 webapp test run: shell timeouts, mcp_search task words, find/diff/csv, code_execute cwd, screenshot save path."""
from __future__ import annotations
import subprocess
import sys
import time
from uuid import uuid4
import pytest
from bootstrap import state
from schemas.tool import ToolCall
from thrall.tools import registry
from thrall.tools.shell.process import run_with_timeout
from thrall.tools.filesystem import find as fs_find, diff as fs_diff
from thrall.tools.documents import read_csv
from thrall.tools.code import execute as code_execute
from thrall.tools.browser import screenshot


def _call(name: str, **args) -> ToolCall:
    return ToolCall(session_id=uuid4(), name=name, args=args, caller="thrall")


@pytest.fixture
def workspace(tmp_path):
    saved = state.get_workspace_dir()
    state.set_workspace_dir(str(tmp_path))
    yield tmp_path
    state.set_workspace_dir(saved)


class TestShellTimeout:
    def test_timeout_kills_grandchild_holding_the_pipe(self):
        """The grandchild inherits stdout. Before the fix, the timeout waited on it forever."""
        child = (
            "import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "time.sleep(60)"
        )
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            run_with_timeout([sys.executable, "-c", child], shell=False, cwd=None, timeout=2, env={**__import__("os").environ})
        assert time.monotonic() - start < 15

    def test_normal_command_returns_output(self):
        code, out, err = run_with_timeout([sys.executable, "-c", "print('hi')"], shell=False, cwd=None, timeout=10,
                                          env={**__import__("os").environ})
        assert code == 0 and out.strip() == "hi"


class TestMcpSearchTaskWords:
    @pytest.fixture(autouse=True)
    def fake_tools(self):
        saved = dict(registry._MCP_TOOLS)
        registry._MCP_TOOLS.clear()
        registry.register_mcp_tools([
            {"type": "function", "function": {"name": n, "description": d, "parameters": {"type": "object", "properties": {}}}}
            for n, d in [
                ("rea__address_name", "Name an address"),
                ("rea__analyze_function", "Analyze a function"),
                ("rea__inspect_dotnet_assembly", "Inspect a managed assembly"),
            ]
        ])
        yield
        registry._MCP_TOOLS.clear()
        registry._MCP_TOOLS.update(saved)

    def test_server_plus_task_word_loads_only_matches(self):
        assert registry.search_mcp("rea dotnet", 8) == ["rea__inspect_dotnet_assembly"]

    def test_unmatched_task_word_loads_nothing(self):
        assert registry.search_mcp("rea zzzz", 8) == []


class TestFilesystem:
    def test_find_extension_without_dot(self, workspace):
        (workspace / "a.txt").write_text("x")
        (workspace / "b.md").write_text("x")
        result = fs_find.execute(_call("filesystem_find", path=".", extension="txt"))
        assert "a.txt" in result.output and "b.md" not in result.output

    def test_diff_last_line_without_newline(self, workspace):
        (workspace / "a.txt").write_text("alpha\nBETA\ngamma")
        (workspace / "b.txt").write_text("alpha\nBETA\ngamma\ndelta")
        out = fs_diff.execute(_call("filesystem_diff", path_a="a.txt", path_b="b.txt")).output
        assert "-gamma+gamma" not in out
        assert "\n+delta" in out


class TestCsv:
    def test_reports_true_total_when_truncated(self, workspace):
        (workspace / "t.csv").write_text("n\n" + "\n".join(str(i) for i in range(66)) + "\n")
        out = read_csv.execute(_call("documents_read_csv", path="t.csv", max_rows=50)).output
        assert "66 rows total, 50 shown" in out
        assert "showing 50 of 66 rows" in out

    def test_untruncated(self, workspace):
        (workspace / "t.csv").write_text("n\n1\n2\n")
        out = read_csv.execute(_call("documents_read_csv", path="t.csv")).output
        assert "2 rows total, 2 shown" in out and "truncated" not in out


class TestCodeExecute:
    @pytest.mark.asyncio
    async def test_runs_in_workspace(self, workspace):
        result = await code_execute.execute(_call("code_execute", code="import os; print(os.getcwd())"))
        assert result.output.strip().lower() == str(workspace).lower()


class TestScreenshotSavePath:
    def test_accepts_new_png_in_workspace(self, workspace):
        target, error = screenshot._save_target("shots/page.png")
        assert error is None and target == workspace / "shots" / "page.png"

    def test_rejects_outside_workspace(self, workspace, tmp_path_factory):
        outside = tmp_path_factory.mktemp("elsewhere") / "x.png"
        assert screenshot._save_target(str(outside))[1] == "save_path must be inside the workspace"

    def test_rejects_existing_file(self, workspace):
        (workspace / "x.png").write_bytes(b"x")
        assert "already exists" in screenshot._save_target("x.png")[1]

    def test_rejects_non_image(self, workspace):
        assert "must end in" in screenshot._save_target("notes.txt")[1]
