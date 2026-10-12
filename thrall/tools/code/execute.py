from __future__ import annotations
import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult
from constants.tools import MAX_OUTPUT, CODE_EXECUTE_DEFAULT_TIMEOUT
from thrall.tools.shell.process import run_with_timeout


def _run_sync(tmp_path: str, cwd: str | None, timeout: int) -> tuple[int, str, str]:
    """Runs in the workspace, like shell_run, so relative paths land in the same place."""
    return run_with_timeout([sys.executable, tmp_path], shell=False, cwd=cwd, timeout=timeout, env=os.environ.copy())


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    code = call.args.get("code", "")
    language = call.args.get("language", "python")
    timeout = int(call.args.get("timeout", CODE_EXECUTE_DEFAULT_TIMEOUT))
    cwd = state.get_workspace_dir() or None

    if language != "python":
        return _result(call.id, error=f"unsupported language: {language}", start=start)

    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        try:
            returncode, out, err = await asyncio.to_thread(_run_sync, tmp_path, cwd, timeout)
        except subprocess.TimeoutExpired:
            return _result(call.id, error=f"execution timed out after {timeout}s", start=start)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if returncode != 0:
            return _result(call.id, error=err[:MAX_OUTPUT] or "non-zero exit", start=start)

        combined = (out + ("\n[stderr]\n" + err if err else ""))[:MAX_OUTPUT]
        return _result(call.id, output=combined or "(no output)", start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "code_execute"
DESCRIPTION = "Execute Python code in a subprocess sandbox. Output is captured and returned. Runs in the workspace directory, so relative paths resolve there."
PARAMETERS = {
    "code": {"type": "string", "required": True},
    "language": {"type": "string", "required": False, "default": "python"},
    "timeout": {"type": "integer", "required": False, "default": 30},
}
