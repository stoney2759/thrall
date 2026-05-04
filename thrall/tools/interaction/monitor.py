from __future__ import annotations
import asyncio
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from bootstrap import state
from constants.tools import MAX_OUTPUT


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    command = call.args.get("command", "").strip()
    timeout = float(call.args.get("timeout_seconds", 30))
    stop_pattern = call.args.get("stop_pattern", "").strip()
    cwd = call.args.get("cwd") or state.get_workspace_dir() or None

    if not command:
        return _result(call.id, error="command is required", start=start)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
    except Exception as e:
        return _result(call.id, error=str(e), start=start)

    lines: list[str] = []
    stop_matched = False

    async def _collect() -> None:
        nonlocal stop_matched
        assert proc.stdout is not None
        while True:
            try:
                raw = await proc.stdout.readline()
            except Exception:
                break
            if not raw:
                break
            text = raw.decode(errors="replace").rstrip()
            lines.append(text)
            if stop_pattern and stop_pattern in text:
                stop_matched = True
                break

    timed_out = False
    try:
        await asyncio.wait_for(_collect(), timeout=timeout)
    except asyncio.TimeoutError:
        timed_out = True

    try:
        proc.terminate()
    except Exception:
        pass

    output = "\n".join(lines) if lines else "(no output)"
    if len(output) > MAX_OUTPUT:
        output = output[-MAX_OUTPUT:]

    if stop_matched:
        output += "\n[stopped: pattern matched]"
    elif timed_out:
        output += "\n[stopped: timeout]"

    return _result(call.id, output=output, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "interaction_monitor"
DESCRIPTION = (
    "Run a command and collect its output, stopping when a pattern is matched or timeout is reached. "
    "Unlike shell_run, returns early when stop_pattern appears — ideal for watching server startup logs "
    "or waiting for a specific condition in streaming output."
)
PARAMETERS = {
    "command": {
        "type": "string",
        "required": True,
        "description": "Shell command to run and monitor",
    },
    "timeout_seconds": {
        "type": "integer",
        "required": False,
        "default": 30,
        "description": "Max seconds to collect output before returning. Default 30.",
    },
    "stop_pattern": {
        "type": "string",
        "required": False,
        "default": "",
        "description": "Return early when this string appears in output. Leave empty to run until timeout or exit.",
    },
    "cwd": {
        "type": "string",
        "required": False,
        "default": "",
        "description": "Working directory. Defaults to workspace.",
    },
}
