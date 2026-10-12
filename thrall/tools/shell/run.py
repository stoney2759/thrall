from __future__ import annotations
import asyncio
import os
import subprocess
import sys
import time
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult
from constants.tools import MAX_OUTPUT, SHELL_DEFAULT_TIMEOUT
from thrall.tools.shell.process import run_with_timeout


def _run_sync(command: str, cwd: str | None, timeout: int, env: dict) -> tuple[int, str, str]:
    return run_with_timeout(command, shell=True, cwd=cwd, timeout=timeout, env=env)


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    command = call.args.get("command", "").strip()
    _cwd = call.args.get("cwd")
    workspace = state.get_workspace_dir()
    if _cwd and not os.path.isabs(_cwd):
        cwd = os.path.join(workspace, _cwd) if workspace else _cwd
    else:
        cwd = _cwd or workspace or None
    timeout = int(call.args.get("timeout", SHELL_DEFAULT_TIMEOUT))

    if not command:
        return _result(call.id, error="command is required", start=start)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    scripts_dir = str(__import__("pathlib").Path(sys.executable).parent)
    env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")

    try:
        returncode, out, err = await asyncio.to_thread(_run_sync, command, cwd, timeout, env)
    except subprocess.TimeoutExpired:
        return _result(call.id, error=f"timed out after {timeout}s — the command and every process it started were killed", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)

    combined = out
    if err:
        combined += f"\n[stderr]\n{err}"
    combined = combined[:MAX_OUTPUT]

    if returncode != 0:
        return _result(call.id, error=f"exit {returncode}\n{combined}", start=start)

    msg = combined if combined else "(no output — normal for destructive commands like rm, del, mv, mkdir)"
    msg += "\n[Verify the result with filesystem_ls or filesystem_stat before reporting completion.]"
    return _result(call.id, output=msg, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "shell_run"
DESCRIPTION = "Run a shell command and return stdout/stderr. cwd defaults to the workspace directory. For GUI smoke tests use a short timeout (5-10s). Default timeout is 300s."
PARAMETERS = {
    "command": {"type": "string", "required": True},
    "cwd": {"type": "string", "required": False, "default": ""},
    "timeout": {"type": "integer", "required": False, "default": 300, "description": "Timeout in seconds. Default 300. Use shorter values (5-10) for GUI smoke tests or long-running daemons."},
}
