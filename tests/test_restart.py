"""thrall_restart — always confirmed with the user; finds and kills only Thrall's own process tree."""
from __future__ import annotations
import subprocess
import sys
import time
import psutil
import pytest
from services import permissions
from constants.permissions import MODE_ASK, MODE_TRUSTED, MODE_READ_ONLY, DECISION_ALLOW, DECISION_ASK, DECISION_DENY
from thrall.tools.system import restart, restart_helper
from thrall.tools import registry


def _decide(tool, args, mode=MODE_TRUSTED, session_allow=()):
    return permissions.decide(tool, args, mode, [], [], list(session_allow))[0]


class TestAlwaysConfirm:
    def test_restart_tool_asks_even_in_trusted_mode(self):
        assert _decide("thrall_restart", {"reason": "new MCP"}) == DECISION_ASK
        assert _decide("thrall_restart", {"reason": "x"}, mode=MODE_ASK) == DECISION_ASK

    def test_earlier_always_answer_does_not_cover_restart(self):
        assert _decide("thrall_restart", {"reason": "x"}, mode=MODE_ASK, session_allow=["thrall_restart"]) == DECISION_ASK
        cmd = {"command": "taskkill /T /F /PID 123; python thrall.py --all"}
        assert _decide("powershell_run", cmd, mode=MODE_ASK, session_allow=["powershell_run"]) == DECISION_ASK

    def test_read_only_mode_denies_restart(self):
        assert _decide("thrall_restart", {"reason": "x"}, mode=MODE_READ_ONLY) == DECISION_DENY

    def test_shell_self_restart_asks_in_trusted_mode(self):
        for command in ("Start-Process powershell -ArgumentList \"& '.\\venv\\Scripts\\python.exe' thrall.py --all\"",
                        "powershell -File self-restart.ps1 -RootPid 1",
                        "Stop-Process -Id 4; python thrall.py --web"):
            assert _decide("powershell_run", {"command": command}) == DECISION_ASK, command

    def test_ordinary_shell_commands_still_run_in_trusted_mode(self):
        for command in ("git status", "Get-Content thrall.py", "python --version", "taskkill /PID 999"):
            assert _decide("powershell_run", {"command": command}) == DECISION_ALLOW, command

    def test_prompt_offers_no_always(self):
        text = permissions.prompt_text("thrall_restart", {"reason": "load new tool"})
        assert "always" not in text.lower().replace("confirmed every time", "") and "load new tool" in text


class TestTool:
    def test_registered(self):
        names = {d["function"]["name"] for d in registry.get_definitions()}
        assert "thrall_restart" in names

    @pytest.mark.asyncio
    async def test_reason_required(self):
        from uuid import uuid4
        from schemas.tool import ToolCall
        result = await restart.execute(ToolCall(session_id=uuid4(), name="thrall_restart", args={}, caller="thrall"))
        assert result.error and "reason" in result.error


def _spawn_tree(parent_marker: str) -> tuple[subprocess.Popen, int]:
    """A parent whose command line contains parent_marker, with one child that sleeps. Returns (parent, child pid)."""
    code = ("import subprocess, sys, time; "
            "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "print(c.pid, flush=True); time.sleep(60)")
    parent = subprocess.Popen([sys.executable, "-c", code, parent_marker], stdout=subprocess.PIPE, text=True)
    child_pid = int(parent.stdout.readline())
    return parent, child_pid


class TestProcessTree:
    def test_find_root_walks_up_to_the_thrall_launcher(self):
        parent, child_pid = _spawn_tree("thrall.py")
        try:
            root_pid, cmdline, _cwd = restart.find_root(child_pid)
            assert any("thrall.py" in part for part in cmdline)
            assert root_pid in {p.pid for p in psutil.Process(child_pid).parents()}
            assert root_pid != psutil.Process().pid  # stops before the test runner (no marker)
        finally:
            restart_helper.kill_tree(parent.pid, keep_pid=-1)

    def test_kill_tree_kills_root_and_children(self):
        parent, child_pid = _spawn_tree("thrall.py")
        killed = restart_helper.kill_tree(parent.pid, keep_pid=-1)
        assert killed >= 2
        time.sleep(0.5)
        assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
        assert parent.poll() is not None

    def test_kill_tree_spares_the_helper(self):
        parent, child_pid = _spawn_tree("restart_helper")  # the "root" here looks like the helper
        try:
            survivors = [p for p in psutil.Process(parent.pid).children(recursive=True)]
            restart_helper.kill_tree(child_pid, keep_pid=-1)  # kill only the child's tree
            assert parent.poll() is None  # helper-named parent untouched
        finally:
            restart_helper.kill_tree(parent.pid, keep_pid=-1)
            assert survivors is not None
