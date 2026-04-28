from __future__ import annotations
import asyncio
import os
import subprocess
import sys
import time
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult

_DEFAULT_TIMEOUT = 60
_MAX_OUTPUT = 16_000


def _run_sync(command: str, cwd: str | None, timeout: int, env: dict) -> tuple[int, str, str]:
    result = subprocess.run(
        ["powershell.exe", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    command = call.args.get("command", "").strip()
    cwd = call.args.get("cwd") or state.get_workspace_dir() or None
    timeout = int(call.args.get("timeout", _DEFAULT_TIMEOUT))

    if not command:
        return _result(call.id, error="command is required", start=start)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    scripts_dir = str(__import__("pathlib").Path(sys.executable).parent)
    env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")

    try:
        returncode, out, err = await asyncio.to_thread(_run_sync, command, cwd, timeout, env)
    except subprocess.TimeoutExpired:
        return _result(call.id, error=f"timed out after {timeout}s", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)

    combined = out
    if err:
        combined += f"\n[stderr]\n{err}"
    combined = combined[:_MAX_OUTPUT]

    if returncode != 0:
        return _result(call.id, error=f"exit {returncode}\n{combined}", start=start)

    return _result(call.id, output=combined or "(no output)", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "shell.powershell"
DESCRIPTION = "Run a PowerShell command on Windows and return stdout/stderr. Use this instead of shell.run for Windows-native commands where bash syntax would fail. cwd defaults to the workspace directory."
PARAMETERS = {
    "command": {"type": "string", "required": True},
    "cwd": {"type": "string", "required": False, "default": ""},
    "timeout": {"type": "integer", "required": False, "default": 60},
}
