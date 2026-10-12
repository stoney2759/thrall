from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult
from constants.restart import RESTART_DELAY_SECONDS, RESTART_ROOT_MARKER, RESTART_DEFAULT_PORT

_ROOT = Path(__file__).resolve().parents[3]


def find_root(pid: int) -> tuple[int, list[str], str]:
    """The top of Thrall's process tree: walk up while the parent's command line names thrall.py
    (so a launcher window running thrall.py is included, the user's own shell is not).
    Returns (root pid, its command line, its working directory)."""
    import psutil
    proc = psutil.Process(pid)
    while True:
        parent = proc.parent()
        if parent is None:
            break
        try:
            cmdline = parent.cmdline()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            break
        if not any(RESTART_ROOT_MARKER in part for part in cmdline):
            break
        proc = parent
    try:
        cwd = proc.cwd()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        cwd = str(_ROOT)
    return proc.pid, proc.cmdline(), cwd


def _spawn_helper(root_pid: int, port: int, cwd: str, command: list[str]) -> int:
    args = [sys.executable, "-m", "thrall.tools.system.restart_helper",
            str(root_pid), str(port), cwd, json.dumps(command)]
    if sys.platform == "win32":
        # Break away from any job object the Thrall launcher created, or killing Thrall kills the helper too
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        quiet = dict(cwd=str(_ROOT), close_fds=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc = subprocess.Popen(args, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **quiet)
        except OSError:  # the job doesn't allow breakaway
            proc = subprocess.Popen(args, creationflags=flags, **quiet)
    else:
        proc = subprocess.Popen(args, cwd=str(_ROOT), start_new_session=True, close_fds=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc.pid


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    reason = str(call.args.get("reason", "")).strip()
    if not reason:
        return _result(call.id, error="reason is required — say why the restart is needed", start=start)
    try:
        root_pid, command, cwd = find_root(os.getpid())
        if not any(RESTART_ROOT_MARKER in part for part in command):
            return _result(call.id, error="could not find Thrall's launcher process — ask the user to restart manually",
                           start=start)
        port = int(state.get_config().get("server", {}).get("port", RESTART_DEFAULT_PORT))
        helper_pid = _spawn_helper(root_pid, port, cwd, command)
    except Exception as e:
        return _result(call.id, error=f"restart failed to start: {e}", start=start)
    output = (
        f"Restart scheduled: in ~{RESTART_DELAY_SECONDS}s the Thrall process tree (root pid {root_pid}) is "
        f"stopped and relaunched with the same command (helper pid {helper_pid}, log: logs/restart.log). "
        f"Reason: {reason}. Tell the user you are restarting now and make NO further tool calls — "
        "anything still running will be cut off."
    )
    return _result(call.id, output=output, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "thrall_restart"
DESCRIPTION = (
    "Restart Thrall itself (stop and relaunch this whole process) — e.g. after editing Thrall's own code, "
    "adding an MCP server or changing config. The user is always asked to confirm first. Use this instead "
    "of writing restart scripts or killing processes with shell tools. Make no tool calls after it."
)
PARAMETERS = {
    "reason": {"type": "string", "required": True, "description": "Why the restart is needed (shown to the user)."},
}
