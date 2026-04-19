from __future__ import annotations
import re
from components.agents.types import AgentDefinition

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


def validate(agent: AgentDefinition, existing_names: list[str]) -> list[str]:
    errors: list[str] = []

    if not _SLUG_RE.match(agent.name):
        errors.append(f"name '{agent.name}' must be lowercase letters, numbers, hyphens, 3-50 chars")

    if agent.name in existing_names:
        errors.append(f"agent '{agent.name}' already exists")

    if len(agent.description) < 10:
        errors.append("description too short — minimum 10 characters")

    if len(agent.soul) < 50:
        errors.append("soul (system prompt) too short — minimum 50 characters")

    return errors
