from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    try:
        from services.browser.manager import close
        await close(call.session_id)
        return _result(call.id, output="Browser session closed.", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser.close"
DESCRIPTION = "Close the current browser session. The next browser.navigate call will open a fresh browser."
PARAMETERS = {}
