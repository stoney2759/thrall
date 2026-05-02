from __future__ import annotations
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult

_DEFAULT_TIMEOUT = 60
_MAX_OUTPUT = 16_000

# Subcommands that modify history or remote state — require explicit confirmation arg
_DESTRUCTIVE = {"push --force", "push -f", "reset --hard", "clean -f", "rebase"}


def _run_sync(command: str, cwd: str, timeout: int) -> tuple[int, str, str]:
    env = os.environ.copy()
    scripts_dir = str(Path(sys.executable).parent)
    env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        f"git {command}", shell=True, capture_output=True,
        text=True, cwd=cwd, timeout=timeout, env=env,
    )
    return result.returncode, result.stdout, result.stderr


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    command = call.args.get("command", "").strip()
    timeout = int(call.args.get("timeout", _DEFAULT_TIMEOUT))
    repo = call.args.get("repo", "").strip() or state.get_workspace_dir() or "."
    confirmed = call.args.get("confirmed", False)

    if not command:
        return _result(call.id, error="command is required (e.g. 'status', 'add -A', 'commit -m \"msg\"')", start=start)

    for destructive in _DESTRUCTIVE:
        if command.startswith(destructive) and not confirmed:
            return _result(call.id, error=f"'{command}' is a destructive operation — pass confirmed=true to proceed", start=start)

    try:
        returncode, out, err = await asyncio.to_thread(_run_sync, command, repo, timeout)
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


NAME = "git_run"
DESCRIPTION = (
    "Run any git command on a local repository. Pass the subcommand and flags directly "
    "(e.g. command='status', command='add -A', command='commit -m \"fix bug\"', "
    "command='push origin main', command='log --oneline -10'). "
    "Prefer this over GitHub MCP for all local repository operations. "
    "Destructive commands (force push, reset --hard, clean -f) require confirmed=true."
)
PARAMETERS = {
    "command":   {"type": "string",  "required": True},
    "repo":      {"type": "string",  "required": False, "default": ""},
    "confirmed": {"type": "boolean", "required": False, "default": False},
    "timeout":   {"type": "integer", "required": False, "default": 60},
}
