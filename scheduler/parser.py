from __future__ import annotations
import json
import re
from dataclasses import dataclass

from scheduler.cron_eval import to_cron_expr, validate


@dataclass
class ParseResult:
    cron_expr: str
    human_summary: str


_LLM_SYSTEM = """\
Convert a schedule description to a standard 5-field cron expression.
Output a JSON object with exactly two fields:
  "cron_expr": a valid 5-field cron expression (minute hour day month weekday)
  "human_summary": plain English confirmation of what the schedule means

Cron weekday convention: 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday

Examples:
  "every monday at 9am"         -> {"cron_expr": "0 9 * * 1", "human_summary": "Every Monday at 9:00 AM"}
  "twice daily at 8am and 6pm"  -> {"cron_expr": "0 8,18 * * *", "human_summary": "Every day at 8:00 AM and 6:00 PM"}
  "first of the month at noon"  -> {"cron_expr": "0 12 1 * *", "human_summary": "1st of every month at 12:00 PM"}
  "every 15 minutes"            -> {"cron_expr": "*/15 * * * *", "human_summary": "Every 15 minutes"}
  "weekdays at 9am"             -> {"cron_expr": "0 9 * * 1-5", "human_summary": "Monday to Friday at 9:00 AM"}

Output JSON only. No explanation, no markdown, no code fences.
"""


def _is_cron_expr(s: str) -> bool:
    return bool(re.fullmatch(r"[\d\*\/\,\-]+ [\d\*\/\,\-]+ [\d\*\/\,\-]+ [\d\*\/\,\-]+ [\d\*\/\,\-]+", s.strip()))


def _strip_brackets(s: str) -> str:
    return re.sub(r"[<>\[\]]", "", s).strip()


async def parse_schedule(raw: str) -> ParseResult:
    """
    Parse a natural language or legacy schedule string into a ParseResult.
    Order of resolution:
      1. Strip stray brackets
      2. If already a valid cron expression — use directly
      3. If matches legacy format (30m, 18:00) — convert without LLM
      4. Otherwise — call LLM
    """
    cleaned = _strip_brackets(raw)

    # Already a cron expression
    if _is_cron_expr(cleaned) and validate(cleaned):
        return ParseResult(
            cron_expr=cleaned,
            human_summary=_summarise_cron(cleaned),
        )

    # Legacy simple format
    cron = to_cron_expr(cleaned)
    if cron:
        return ParseResult(
            cron_expr=cron,
            human_summary=_summarise_cron(cron),
        )

    # Natural language — call LLM
    return await _llm_parse(cleaned)


async def _llm_parse(raw: str) -> ParseResult:
    from services.llm import client as llm

    messages = [
        {"role": "system", "content": _LLM_SYSTEM},
        {"role": "user", "content": raw},
    ]
    response = await llm.complete(messages=messages)

    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?", "", response).strip().rstrip("```").strip()

    try:
        data = json.loads(text)
        cron_expr = data.get("cron_expr", "").strip()
        human_summary = data.get("human_summary", raw)
        if not validate(cron_expr):
            raise ValueError(f"Invalid cron expression: {cron_expr}")
        return ParseResult(cron_expr=cron_expr, human_summary=human_summary)
    except Exception as e:
        raise ValueError(f"Could not parse schedule '{raw}': {e}\nLLM response: {response[:200]}")


def _summarise_cron(expr: str) -> str:
    """Best-effort human summary for simple cron expressions without calling LLM."""
    fields = expr.strip().split()
    if len(fields) != 5:
        return expr

    f_min, f_hour, f_dom, f_month, f_dow = fields

    # Every N minutes
    if f_min.startswith("*/") and f_hour == "*" and f_dom == "*" and f_month == "*" and f_dow == "*":
        return f"Every {f_min[2:]} minutes"

    if f_min == "*" and f_hour == "*":
        return "Every minute"

    # Daily at HH:MM
    if f_dom == "*" and f_month == "*" and f_dow == "*" and re.fullmatch(r"\d+", f_hour) and re.fullmatch(r"\d+", f_min):
        h, m = int(f_hour), int(f_min)
        return f"Every day at {h:02d}:{m:02d}"

    # Weekly
    _days = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
    if f_dom == "*" and f_month == "*" and re.fullmatch(r"\d", f_dow):
        day = _days.get(int(f_dow), f_dow)
        if re.fullmatch(r"\d+", f_hour) and re.fullmatch(r"\d+", f_min):
            h, m = int(f_hour), int(f_min)
            return f"Every {day} at {h:02d}:{m:02d}"

    return expr
