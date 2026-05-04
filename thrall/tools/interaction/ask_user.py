from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    question = call.args.get("question", "").strip()
    timeout = float(call.args.get("timeout_seconds", 300))

    if not question:
        return _result(call.id, error="question is required", start=start)

    from services import ask_user_channel
    reply = await ask_user_channel.ask(call.session_id, question, timeout_seconds=timeout)
    return _result(call.id, output=reply, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "interaction_ask_user"
DESCRIPTION = (
    "Ask the user a question and wait for their reply before continuing. "
    "Use when you need clarification, a decision, or user input mid-task. "
    "The question is sent directly to the user; the tool blocks until they reply or timeout."
)
PARAMETERS = {
    "question": {
        "type": "string",
        "required": True,
        "description": "The question to ask the user",
    },
    "timeout_seconds": {
        "type": "integer",
        "required": False,
        "default": 300,
        "description": "Seconds to wait for a reply before timing out. Default 300.",
    },
}
