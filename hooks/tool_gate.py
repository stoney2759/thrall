from __future__ import annotations
from schemas.tool import ToolCall, GateDecision
from schemas.task import CapabilityProfile
from hooks import audit

# Tools that require explicit capability profile permission (never available by default)
_RESTRICTED_TOOLS: set[str] = {
    "code.execute",
    "shell.run",
    "filesystem.write",
    "filesystem.edit",
    "agents.spawn",
}

# Tools always available to Thrall directly (no profile needed)
_ALWAYS_ALLOWED: set[str] = {
    "filesystem.read",
    "filesystem.glob",
    "filesystem.grep",
    "web.search",
    "web.fetch",
    "web.scrape",
    "web.browse",
    "memory.read",
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
