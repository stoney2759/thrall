"""Hand a finished background task back to Thrall's reasoning loop.

Previously a finished task's raw result was posted straight to the user. Now the result is
sent into the session that started the task as a message, so Thrall reasons about it and
replies. If Thrall is busy in that session, the result is queued into the running task
(services.interjections) and there is nothing to send yet.
"""
from __future__ import annotations
from schemas.message import Message, Role, Transport
from schemas.task import Task, TaskStatus
from constants.agents import BACKGROUND_RESULT_MAX_CHARS, BACKGROUND_RESULT_HEADER, BACKGROUND_RESULT_INSTRUCTION
from constants.coordinator import INTERJECTION_ACK


def should_wake(task: Task) -> bool:
    return (
        task.session_id is not None
        and not task.silent
        and task.status in (TaskStatus.DONE, TaskStatus.FAILED)
    )


def build_notice(task: Task) -> str:
    profile = task.profile.name if task.profile else "default"
    if task.status == TaskStatus.DONE:
        body = task.result or "(the task completed but returned no output)"
        status = "done"
    else:
        body = task.error or "(no error details)"
        status = "failed"
    if len(body) > BACKGROUND_RESULT_MAX_CHARS:
        body = body[:BACKGROUND_RESULT_MAX_CHARS] + f"\n[cut — {len(body):,} chars total; full result: agents_result {task.id}]"
    return (
        f"{BACKGROUND_RESULT_HEADER}\n"
        f"Task: {task.id} (profile: {profile}) — status: {status}\n"
        f"Brief: {task.brief[:300]}\n\n"
        f"Result:\n{body}\n\n"
        f"{BACKGROUND_RESULT_INSTRUCTION}"
    )


async def wake(task: Task, transport: Transport, user_id: str) -> str | None:
    """Run Thrall on the task's result. Returns the reply to send, or None if it was queued mid-task."""
    # coordinator imports services at module load, so it is imported at call time here
    from thrall.coordinator import receive

    message = Message(
        session_id=task.session_id,
        role=Role.USER,
        content=build_notice(task),
        transport=transport,
        user_id=user_id,
    )
    reply = await receive(message)
    return None if reply == INTERJECTION_ACK else reply
