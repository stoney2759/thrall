from __future__ import annotations
import asyncio
import re
import uuid
from datetime import datetime, timezone

from scheduler.job import Job
from scheduler import store
from scheduler.cron_eval import is_due, to_cron_expr
from bootstrap import state

_bot = None
_SCHEDULER_SESSION = uuid.uuid5(uuid.NAMESPACE_DNS, "thrall:scheduler")
_POLL_INTERVAL = 60  # seconds


def set_bot(bot) -> None:
    global _bot
    _bot = bot


async def _push(text: str) -> None:
    if _bot is None:
        return
    allowed: list = state.get_config().get("transports", {}).get("telegram", {}).get("allowed_user_ids", [])
    for uid in allowed:
        try:
            await _bot.send_message(chat_id=uid, text=text)
        except Exception:
            pass


def _parse_interval_seconds(schedule: str) -> int | None:
    m = re.fullmatch(r"(\d+)(s|m|h|d)", schedule.strip().lower())
    if not m:
        return None
    val, unit = int(m.group(1)), m.group(2)
    return val * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _get_cron_expr(job: Job) -> str | None:
    """Resolve the cron expression for a job, falling back to legacy conversion."""
    if job.cron_expr:
        return job.cron_expr
    return to_cron_expr(job.schedule)


def _should_fire(job: Job, now: datetime) -> bool:
    if not job.enabled:
        return False

    cron_expr = _get_cron_expr(job)
    if not cron_expr:
        return False

    if not is_due(cron_expr, now):
        return False

    if job.last_run is None:
        return True

    last = datetime.fromisoformat(job.last_run)
    # Never re-fire within the same minute
    return not (last.year == now.year and last.month == now.month and
                last.day == now.day and last.hour == now.hour and
                last.minute == now.minute)


async def _fire_job(job: Job) -> None:
    from schemas.message import Message, Role, Transport
    from thrall.coordinator import receive

    ts = datetime.now().astimezone().isoformat()
    task = job.task
    if job.agent:
        task = f"Use agent '{job.agent}' to: {task}"

    await _push(f"[{job.type.upper()}] Job `{job.id}` started — {job.task[:80]}")

    try:
        msg = Message(
            session_id=_SCHEDULER_SESSION,
            role=Role.USER,
            content=task,
            transport=Transport.SCHEDULER,
            user_id="scheduler",
        )
        response = await receive(msg)
        store.update_last_run(job.id, ts)

        if job.output_mode == "verbose":
            await _push(f"[{job.type.upper()}] Job `{job.id}` completed:\n{response}")
        else:
            summary = response.splitlines()[0][:120] if response else "done"
            await _push(f"[{job.type.upper()}] Job `{job.id}` completed — {summary}")

    except Exception as e:
        store.update_last_run(job.id, ts)
        await _push(f"[{job.type.upper()}] Job `{job.id}` failed: {e}")


async def _run_loop() -> None:
    while True:
        await asyncio.sleep(_POLL_INTERVAL)
        now = datetime.now().astimezone()
        try:
            jobs = store.load_jobs()
            for job in jobs:
                if _should_fire(job, now):
                    asyncio.create_task(_fire_job(job))
        except Exception as e:
            state.log_error(f"Scheduler runner error: {e}")


def start(bot) -> None:
    set_bot(bot)
    asyncio.get_event_loop().create_task(_run_loop())
