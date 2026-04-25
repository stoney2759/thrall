from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from hooks.input_gate import INJECTION_PATTERNS
from hooks import audit

logger = logging.getLogger(__name__)

# Patterns specific to system-context poisoning — things that wouldn't appear in
# normal personality descriptions but would in an injection or bypass attempt.
_PROFILE_PATTERNS: list[re.Pattern] = [
    # SOUL.md / RULES.md bypass attempts
    re.compile(r"soul\.?md\s*(does not|doesn'?t|no longer)\s*apply", re.IGNORECASE),
    re.compile(r"(ignore|override|bypass|disregard)\s+(your\s+)?(soul|rules|identity)", re.IGNORECASE),
    re.compile(r"rules?\s+(are\s+)?(lifted|removed|suspended|disabled)", re.IGNORECASE),
    re.compile(r"(forget|abandon|drop)\s+(your\s+)?(identity|soul|core\s+rules?)", re.IGNORECASE),
    # Permission / capability escalation
    re.compile(r"all\s+restrictions?\s+(are\s+)?(removed|lifted|gone|disabled)", re.IGNORECASE),
    re.compile(r"you\s+have\s+(full|unrestricted|complete)\s+(access|capabilities?|permissions?)", re.IGNORECASE),
    re.compile(r"no\s+(restrictions?|limitations?|constraints?|rules?)\s+apply", re.IGNORECASE),
    re.compile(r"(unrestricted|unconstrained|unfiltered)\s+mode", re.IGNORECASE),
    # Identity takeover
    re.compile(r"you\s+have\s+become\s+", re.IGNORECASE),
    re.compile(r"your\s+true\s+self\s+is", re.IGNORECASE),
    re.compile(r"(forget|abandon)\s+(that\s+you\s+are|being)\s+thrall", re.IGNORECASE),
    # Structured injection markers not covered by input_gate
    re.compile(r"###\s*(override|system|inject|bypass)", re.IGNORECASE),
    re.compile(r"---\s*(system|override|inject)", re.IGNORECASE),
    re.compile(r"<system>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
]

_ALL_PATTERNS = INJECTION_PATTERNS + _PROFILE_PATTERNS


@dataclass
class ProfileScanResult:
    allowed: bool
    profile_name: str
    matched_pattern: str | None = None
    reason: str | None = None


def scan(content: str, profile_name: str) -> ProfileScanResult:
    for pattern in _ALL_PATTERNS:
        match = pattern.search(content)
        if match:
            matched = match.group(0)
            reason = f"profile '{profile_name}' failed security scan — pattern: {pattern.pattern!r} matched: {matched!r}"
            logger.warning(f"[profile_gate] REJECTED — {reason}")
            audit.log_deny("profile_gate", reason=reason)
            return ProfileScanResult(
                allowed=False,
                profile_name=profile_name,
                matched_pattern=matched,
                reason=reason,
            )

    audit.log_allow("profile_gate", reason=f"profile '{profile_name}' passed security scan")
    return ProfileScanResult(allowed=True, profile_name=profile_name)
