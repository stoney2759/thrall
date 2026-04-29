from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).parent.parent / "logs" / "sessions"


def _log_file() -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    return _LOG_DIR / f"{date}.jsonl"


def _write(entry: dict) -> None:
    try:
        with _log_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("Session log write failed: %s", e)


def log_message(session_id: str, role: str, content: str) -> None:
    _write({
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": str(session_id),
        "type": "message",
        "role": role,
        "content": content,
    })


def log_tool_call(session_id: str, tool: str, args: dict) -> None:
    _write({
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": str(session_id),
        "type": "tool_call",
        "tool": tool,
        "args": args,
    })


def log_tool_result(session_id: str, tool: str, output: str, error: str | None = None, duration_ms: int = 0) -> None:
    _write({
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": str(session_id),
        "type": "tool_result",
        "tool": tool,
        "output": output[:2000] if output else None,
        "error": error,
        "duration_ms": duration_ms,
    })


def log_error(session_id: str, error: str) -> None:
    _write({
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": str(session_id),
        "type": "error",
        "error": error,
    })
