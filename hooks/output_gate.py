from __future__ import annotations
import re
from dataclasses import dataclass
from hooks import audit

# Patterns that suggest accidental secret exposure
_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),                          # OpenAI keys
    re.compile(r"sk-or-[a-zA-Z0-9]{20,}", re.IGNORECASE),                       # OpenRouter keys
    re.compile(r"sk-ant-api\d{2}-[a-zA-Z0-9_\-]{90,}", re.IGNORECASE),          # Anthropic keys
    re.compile(r"AIza[0-9A-Za-z\-_]{35}", re.IGNORECASE),                       # Google API keys
    re.compile(r"[a-zA-Z0-9]{32}:[a-zA-Z0-9_\-]{32}", re.IGNORECASE),           # Generic token pairs
    re.compile(r"AKIA[0-9A-Z]{16}"),                                             # AWS access keys
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),                                          # GitHub PAT classic
    re.compile(r"github_pat_[a-zA-Z0-9_]{50,}"),                                 # GitHub PAT fine-grained
    re.compile(r"ghs_[a-zA-Z0-9]{36}"),                                          # GitHub server token
    re.compile(r"\d{8,10}:[A-Za-z0-9_\-]{35}"),                                  # Telegram bot token
    re.compile(r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),       # JWT tokens
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),            # Private key headers
]

_MAX_RESPONSE_LENGTH = 32_000


@dataclass
class OutputResult:
    allowed: bool
    content: str
    reason: str | None = None


def run(content: str) -> OutputResult:
    if not content or not content.strip():
        audit.log_deny("output_gate", reason="empty response")
        return OutputResult(allowed=False, content=content, reason="empty response")

    cleaned, secrets_found = _scrub_secrets(content)

    if secrets_found:
        audit.log_deny("output_gate", reason="secrets scrubbed from response")

    if len(cleaned) > _MAX_RESPONSE_LENGTH:
        cleaned = cleaned[:_MAX_RESPONSE_LENGTH] + "\n\n[truncated]"
        audit.log_allow("output_gate", reason="response truncated to limit")
    else:
        audit.log_allow("output_gate", reason="response passed")

    return OutputResult(allowed=True, content=cleaned)


def _scrub_secrets(content: str) -> tuple[str, bool]:
    found = False
    cleaned = content
    for pattern in _SECRET_PATTERNS:
        if pattern.search(cleaned):
            found = True
            cleaned = pattern.sub("[SECRET REDACTED]", cleaned)
    return cleaned, found
