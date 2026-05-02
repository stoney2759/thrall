from __future__ import annotations
import asyncio
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

_DEFAULT_TIMEOUT = 30
_MAX_OUTPUT = 16_000


def _run_sync(tmp_path: str, timeout: int) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, tmp_path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    code = call.args.get("code", "")
    language = call.args.get("language", "python")
    timeout = int(call.args.get("timeout", _DEFAULT_TIMEOUT))

    if language != "python":
        return _result(call.id, error=f"unsupported language: {language}", start=start)

    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        try:
            returncode, out, err = await asyncio.to_thread(_run_sync, tmp_path, timeout)
        except subprocess.TimeoutExpired:
            return _result(call.id, error=f"execution timed out after {timeout}s", start=start)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if returncode != 0:
            return _result(call.id, error=err[:_MAX_OUTPUT] or "non-zero exit", start=start)

        combined = (out + ("\n[stderr]\n" + err if err else ""))[:_MAX_OUTPUT]
        return _result(call.id, output=combined or "(no output)", start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "code_execute"
DESCRIPTION = "Execute Python code in a subprocess sandbox. Output is captured and returned."
PARAMETERS = {
    "code": {"type": "string", "required": True},
    "language": {"type": "string", "required": False, "default": "python"},
    "timeout": {"type": "integer", "required": False, "default": 30},
}
