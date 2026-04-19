from __future__ import annotations
import asyncio
import tempfile
import time
from pathlib import Path
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

_DEFAULT_TIMEOUT = 30
_MAX_OUTPUT = 16_000


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    code = call.args.get("code", "")
    language = call.args.get("language", "python")
    timeout = call.args.get("timeout", _DEFAULT_TIMEOUT)

    if language != "python":
        return _result(call.id, error=f"unsupported language: {language}", start=start)

    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        proc = await asyncio.create_subprocess_exec(
            "python", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return _result(call.id, error=f"execution timed out after {timeout}s", start=start)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        output = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace")

        if proc.returncode != 0:
            return _result(call.id, error=err[:_MAX_OUTPUT] or "non-zero exit", start=start)

        combined = (output + ("\n[stderr]\n" + err if err else ""))[:_MAX_OUTPUT]
        return _result(call.id, output=combined or "(no output)", start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "code.execute"
DESCRIPTION = "Execute Python code in a subprocess sandbox. Output is captured and returned."
PARAMETERS = {
    "code": {"type": "string", "required": True},
    "language": {"type": "string", "required": False, "default": "python"},
    "timeout": {"type": "integer", "required": False, "default": 30},
}
