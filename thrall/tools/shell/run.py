from __future__ import annotations
import asyncio
import os
import sys
import time
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult

_DEFAULT_TIMEOUT = 300
_MAX_OUTPUT = 16_000


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
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return _result(call.id, error=f"timed out after {timeout}s", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)

    out = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()
    combined = out
    if err:
        combined += f"\n[stderr]\n{err}"
    combined = combined[:_MAX_OUTPUT]

    if proc.returncode != 0:
        return _result(call.id, error=f"exit {proc.returncode}\n{combined}", start=start)

    return _result(call.id, output=combined or "(no output)", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "shell.run"
DESCRIPTION = "Run a shell command and return stdout/stderr. cwd defaults to the workspace directory. For GUI smoke tests use a short timeout (5-10s). Default timeout is 300s."
PARAMETERS = {
    "command": {"type": "string", "required": True},
    "cwd": {"type": "string", "required": False, "default": ""},
    "timeout": {"type": "integer", "required": False, "default": 300, "description": "Timeout in seconds. Default 300. Use shorter values (5-10) for GUI smoke tests or long-running daemons."},
}
