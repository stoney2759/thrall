from __future__ import annotations
from schemas.tool import ToolCall, GateDecision
from schemas.task import CapabilityProfile
from hooks import audit

# Tools that require explicit capability profile permission (never available by default).
# Names match the registry (underscore form) — the old dotted names never matched a real tool.
# Thrall's own calls are further checked by services/permissions (ask / trusted / read_only).
_RESTRICTED_TOOLS: set[str] = {
    "code_execute",
    "shell_run",
    "powershell_run",
    "filesystem_write",
    "filesystem_edit",
    "filesystem_append",
    "agents_spawn",
}

# Tools always available to any caller (read-only, no profile needed)
_ALWAYS_ALLOWED: set[str] = {
    "filesystem_read",
    "filesystem_glob",
    "filesystem_grep",
    "web_search",
    "web_fetch",
    "web_scrape",
    "web_browse",
    "memory_read",
}


def check(call: ToolCall, profile: CapabilityProfile | None = None) -> GateDecision:
    tool = call.name

    if tool in _ALWAYS_ALLOWED:
        audit.log_allow("tool_gate", call, reason=f"{tool} always allowed")
        return GateDecision.ALLOW

    if profile is not None and tool in profile.allowed_tools:
        audit.log_allow("tool_gate", call, reason=f"{tool} permitted by profile '{profile.name}'")
        return GateDecision.ALLOW

    # Thrall has full trust — unrestricted access to all tools
    if call.caller == "thrall":
        audit.log_allow("tool_gate", call, reason="thrall has full tool access")
        return GateDecision.ALLOW

    if tool in _RESTRICTED_TOOLS and profile is None:
        audit.log_deny("tool_gate", call, reason=f"{tool} requires capability profile")
        return GateDecision.DENY

    if profile is not None and tool not in profile.allowed_tools:
        audit.log_deny("tool_gate", call, reason=f"{tool} not in profile '{profile.name}'")
        return GateDecision.DENY

    audit.log_deny("tool_gate", call, reason=f"unknown tool {tool} denied for caller {call.caller}")
    return GateDecision.DENY


def is_allowed(call: ToolCall, profile: CapabilityProfile | None = None) -> bool:
    return check(call, profile) == GateDecision.ALLOW
