from __future__ import annotations
import json
import logging
import re

logger = logging.getLogger(__name__)

# Tools available for assignment — must stay in sync with registry.py
_AVAILABLE_TOOLS = [
    "filesystem.read", "filesystem.write", "filesystem.edit", "filesystem.append",
    "filesystem.glob", "filesystem.grep", "filesystem.cat", "filesystem.ls",
    "filesystem.tree", "filesystem.stat", "filesystem.find", "filesystem.diff",
    "web.search", "web.fetch", "web.scrape", "web.browse",
    "code.execute",
    "memory.read", "memory.write",
    "shell.run",
    "agents.spawn", "agents.result", "agents.await_all", "agents.list", "agents.create",
    "scheduler.add", "scheduler.list", "scheduler.delete",
]

_INFERENCE_PROMPT = f"""\
You are a tool assignment system for AI agents.

Given an agent's system prompt (soul), select ONLY the tools it genuinely needs from this list:
{", ".join(_AVAILABLE_TOOLS)}

Rules:
- Select the minimum set required — do not add tools speculatively.
- filesystem.read is needed if the agent reads files or code.
- filesystem.write / filesystem.edit are needed if the agent writes or modifies files.
- filesystem.grep / filesystem.glob are needed if the agent searches codebases.
- web.search / web.fetch / web.scrape / web.browse are needed if the agent researches the web.
- code.execute is needed if the agent runs or tests code.
- shell.run is needed if the agent runs shell commands or build tools.
- memory.read / memory.write if the agent builds knowledge across sessions.
- agents.spawn if the agent orchestrates other agents.
- scheduler.add / scheduler.list / scheduler.delete if the agent manages scheduled tasks.
- Always include memory.read and memory.write for agents that learn or track state over time.

Return ONLY a valid JSON array of tool name strings. No explanation, no preamble:
["tool1", "tool2"]
"""


async def infer_tools(soul: str) -> list[str]:
    """Infer appropriate allowed_tools for an agent from its soul/instructions."""
    from services.llm import client as llm
    from bootstrap import state

    agents_cfg = state.get_config().get("agents", {})
    model = agents_cfg.get("tier_lightweight", "google/gemini-2.0-flash-lite")

    messages = [
        {"role": "system", "content": _INFERENCE_PROMPT},
        {"role": "user", "content": f"Agent soul:\n\n{soul[:4000]}"},
    ]

    try:
        raw = await llm.complete(messages, model=model)
        tools = _parse(raw)
        # Filter to only registered tools — drop anything hallucinated
        valid = [t for t in tools if t in _AVAILABLE_TOOLS]
        logger.info(f"Tool inference assigned: {valid}")
        return valid
    except Exception as e:
        logger.warning(f"Tool inference failed: {e} — returning safe read-only default")
        return ["filesystem.read", "filesystem.grep", "filesystem.glob",
                "web.search", "web.fetch", "memory.read", "memory.write"]


def _parse(text: str) -> list[str]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if isinstance(parsed, list):
        return [str(t) for t in parsed]
    raise ValueError(f"Expected JSON array, got {type(parsed)}")
