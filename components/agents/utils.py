from __future__ import annotations
from pathlib import Path
from components.agents.types import AgentDefinition

_CATALOG_DIR = Path(__file__).parent.parent.parent / "components" / "agents" / "catalog"


def _catalog_path(name: str) -> Path:
    return _CATALOG_DIR / f"{name}.toml"


def save_agent(agent: AgentDefinition) -> Path:
    _CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    path = _catalog_path(agent.name)
    path.write_text(_to_toml(agent), encoding="utf-8")
    return path


def load_agent(name: str) -> AgentDefinition | None:
    path = _catalog_path(name)
    if not path.exists():
        return None
    return _from_toml(path.read_text(encoding="utf-8"))


def list_agents() -> list[AgentDefinition]:
    if not _CATALOG_DIR.exists():
        return []
    agents = []
    for path in sorted(_CATALOG_DIR.glob("*.toml")):
        try:
            agents.append(_from_toml(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return agents


def list_agent_names() -> list[str]:
    return [a.name for a in list_agents()]


def delete_agent(name: str) -> bool:
    path = _catalog_path(name)
    if path.exists():
        path.unlink()
        return True
    return False


def _to_toml(agent: AgentDefinition) -> str:
    tools_str = ", ".join(f'"{t}"' for t in agent.allowed_tools)
    soul_escaped = agent.soul.replace('"""', '\\"\\"\\"')
    return f'''name = "{agent.name}"
description = "{agent.description}"
model = "{agent.model}"
created_at = "{agent.created_at}"
allowed_tools = [{tools_str}]

soul = """
{soul_escaped}
"""
'''


def _from_toml(text: str) -> AgentDefinition:
    import re

    def _get(key: str) -> str:
        m = re.search(rf'^{key}\s*=\s*"([^"]*)"', text, re.MULTILINE)
        return m.group(1) if m else ""

    def _get_list(key: str) -> list[str]:
        m = re.search(rf'^{key}\s*=\s*\[([^\]]*)\]', text, re.MULTILINE)
        if not m:
            return []
        return [v.strip().strip('"') for v in m.group(1).split(",") if v.strip()]

    def _get_multiline(key: str) -> str:
        m = re.search(rf'^{key}\s*=\s*"""\n([\s\S]*?)\n"""', text, re.MULTILINE)
        return m.group(1).strip() if m else ""

    soul = _get_multiline("soul")
    dev_instructions = _get_multiline("developer_instructions")
    if dev_instructions:
        soul = soul + "\n\n" + dev_instructions

    return AgentDefinition(
        name=_get("name"),
        description=_get("description"),
        model=_get("model"),
        created_at=_get("created_at"),
        allowed_tools=_get_list("allowed_tools"),
        soul=soul,
    )
