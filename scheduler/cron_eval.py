from __future__ import annotations
import re
from datetime import datetime


def _get_cron_weekday(dt: datetime) -> int:
    """Python weekday() is 0=Mon. Standard cron is 0=Sun. Convert."""
    return (dt.weekday() + 1) % 7


def _matches(field: str, value: int) -> bool:
    if field == "*":
        return True

    for part in field.split(","):
        if "/" in part:
            range_part, step = part.split("/", 1)
            try:
                step = int(step)
                if range_part == "*":
                    lo, hi = 0, 59
                elif "-" in range_part:
                    lo, hi = (int(x) for x in range_part.split("-", 1))
                else:
                    lo = hi = int(range_part)
                if lo <= value <= hi and (value - lo) % step == 0:
                    return True
            except ValueError:
                pass
        elif "-" in part:
            try:
                lo, hi = (int(x) for x in part.split("-", 1))
                if lo <= value <= hi:
                    return True
            except ValueError:
                pass
        else:
            try:
                if int(part) == value:
                    return True
            except ValueError:
                pass

    return False


def is_due(cron_expr: str, now: datetime) -> bool:
    """Return True if the cron expression matches the given datetime (to the minute)."""
    try:
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            return False
        f_min, f_hour, f_dom, f_month, f_dow = fields
        return (
            _matches(f_min, now.minute)
            and _matches(f_hour, now.hour)
            and _matches(f_dom, now.day)
            and _matches(f_month, now.month)
            and _matches(f_dow, _get_cron_weekday(now))
        )
    except Exception:
        return False


def to_cron_expr(schedule: str) -> str | None:
    """
    Convert legacy simple schedule strings to cron expressions.
    Returns None if not a recognised legacy format — caller should use LLM.
    """
    s = schedule.strip().lower()

    # Interval: 30m, 2h, 1d, 45s
    m = re.fullmatch(r"(\d+)(s|m|h|d)", s)
    if m:
        val, unit = int(m.group(1)), m.group(2)
        if unit == "s":
            return "* * * * *"
        if unit == "m":
            return "* * * * *" if val == 1 else f"*/{val} * * * *"
        if unit == "h":
            return f"0 */{val} * * *"
        if unit == "d":
            return f"0 0 */{val} * *"

    # Time only: 18:00, 9:00
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        return f"{minute} {hour} * * *"

    return None


def validate(cron_expr: str) -> bool:
    """Basic structural validation — 5 whitespace-separated fields."""
    return len(cron_expr.strip().split()) == 5
