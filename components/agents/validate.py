from __future__ import annotations
import re
from components.agents.types import AgentDefinition

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
_MIN_SOUL_LENGTH = 300  # anything shorter is not a real system prompt
_SOUL_REQUIRED_PHRASES = ["you are", "you will"]  # persona + behavioral guidance


def validate(agent: AgentDefinition, existing_names: list[str]) -> list[str]:
    errors: list[str] = []

    # Name
    if not _SLUG_RE.match(agent.name):
        errors.append(f"name '{agent.name}' must be lowercase letters, numbers, hyphens, 3–50 chars")
    if agent.name in existing_names:
        errors.append(f"agent '{agent.name}' already exists")

    # Description
    if not agent.description.lower().startswith("use this agent when"):
        errors.append("description must start with 'Use this agent when...'")
    if len(agent.description) < 20:
        errors.append("description too short — be specific about when to use this agent")

    # Soul
    soul_lower = agent.soul.lower()
    if len(agent.soul) < _MIN_SOUL_LENGTH:
        errors.append(f"soul too short ({len(agent.soul)} chars) — minimum {_MIN_SOUL_LENGTH}. A real system prompt needs persona, methodology, and output format.")
    for phrase in _SOUL_REQUIRED_PHRASES:
        if phrase not in soul_lower:
            errors.append(f"soul missing '{phrase}' — must establish persona and behavioral guidance")

    # Tools
    invalid_tools = _check_tools(agent.allowed_tools)
    for t in invalid_tools:
        errors.append(f"tool '{t}' not registered — check thrall/tools/registry.py")

    # Model
    if not agent.model or not agent.model.strip():
        errors.append("model is empty — must be a valid model identifier")
    if "/" not in agent.model:
        errors.append(f"model '{agent.model}' looks invalid — expected format: 'provider/model-name'")

    return errors


def _check_tools(tools: list[str]) -> list[str]:
    """Return tool names not present in the live registry."""
    try:
        from thrall.tools.registry import list_tools
        registered = set(list_tools())
        return [t for t in tools if t not in registered]
    except Exception:
        # Registry unavailable at validation time — skip tool check
        return []
