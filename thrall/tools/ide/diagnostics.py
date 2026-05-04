from __future__ import annotations
import asyncio
import shutil
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve
from bootstrap import state
from constants.tools import MAX_OUTPUT

_TIMEOUT = 60


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path_str = call.args.get("path", "").strip()
    tool = call.args.get("tool", "auto").strip().lower()
    extra_args = call.args.get("args", "").strip()

    target = resolve(path_str) if path_str else None

    # Auto-select: prefer ruff, then mypy, then pylint
    if tool == "auto":
        if shutil.which("ruff"):
            tool = "ruff"
        elif shutil.which("mypy"):
            tool = "mypy"
        elif shutil.which("pylint"):
            tool = "pylint"
        else:
            return _result(call.id, error="No linter found. Install ruff: pip install ruff", start=start)

    if not shutil.which(tool):
        return _result(call.id, error=f"'{tool}' not found on PATH. Install it first.", start=start)

    target_arg = str(target) if target else "."

    if tool == "ruff":
        cmd = f'ruff check {target_arg} {extra_args}'.strip()
    elif tool == "mypy":
        cmd = f'mypy {target_arg} --no-error-summary {extra_args}'.strip()
    elif tool == "pylint":
        cmd = f'pylint {target_arg} --output-format=text {extra_args}'.strip()
    else:
        cmd = f'{tool} {target_arg} {extra_args}'.strip()

    cwd = state.get_workspace_dir() or None

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
        except asyncio.TimeoutError:
            proc.terminate()
            return _result(call.id, error=f"timed out after {_TIMEOUT}s", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)

    output = stdout.decode(errors="replace").strip()
    if not output:
        output = f"No issues found ({tool})"
    elif len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + f"\n[truncated — {len(output) - MAX_OUTPUT} chars omitted]"

    output = f"[{tool} — exit {proc.returncode}]\n{output}"
    return _result(call.id, output=output, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "ide_diagnostics"
DESCRIPTION = (
    "Run a linter or type-checker and return diagnostics for a file or directory. "
    "Auto-selects ruff → mypy → pylint based on what's installed. "
    "Pass tool='mypy' or tool='ruff' to force a specific checker."
)
PARAMETERS = {
    "path": {
        "type": "string",
        "required": False,
        "default": "",
        "description": "File or directory to check. Defaults to workspace root.",
    },
    "tool": {
        "type": "string",
        "required": False,
        "default": "auto",
        "description": "Linter to use: auto | ruff | mypy | pylint. Default auto (picks first available).",
    },
    "args": {
        "type": "string",
        "required": False,
        "default": "",
        "description": "Extra CLI arguments passed directly to the linter (e.g. '--select E,W' for ruff).",
    },
}
