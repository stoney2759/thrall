from __future__ import annotations
import re
from dataclasses import dataclass
from schemas.message import Message, Transport
from services.auth import auth
from hooks import audit

# Patterns that suggest prompt injection attempts from external content
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"forget\s+everything", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"disregard\s+(your\s+)?(previous|prior|all)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+are", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.IGNORECASE),
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
]


@dataclass
class InputResult:
    allowed: bool
    content: str
    reason: str | None = None


def run(message: Message) -> InputResult:
    # Gate 1: auth check
    if not auth.is_authorised(message.user_id, message.transport):
        audit.log_deny("input_gate", reason=f"unauthorised user: {message.user_id}")
        return InputResult(allowed=False, content=message.content, reason="unauthorised")

    # Gate 2: sanitize
    cleaned, injections_found = _sanitize(message.content)
    if injections_found:
        audit.log_deny(
            "input_gate",
            reason=f"prompt injection stripped from user message: {message.user_id}",
        )
        # Strip but still allow — we cleaned it, Thrall sees the safe version
        audit.log_allow("input_gate", reason="sanitized content passed through")
        return InputResult(allowed=True, content=cleaned, reason="sanitized")

    audit.log_allow("input_gate", reason="authorised and clean")
    return InputResult(allowed=True, content=cleaned)


def sanitize_external(content: str) -> str:
    cleaned, _ = _sanitize(content)
    return cleaned


def _sanitize(content: str) -> tuple[str, bool]:
    found = False
    cleaned = content
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            found = True
            cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned, found
