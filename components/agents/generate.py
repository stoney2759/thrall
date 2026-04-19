from __future__ import annotations
import json
import re
from components.agents.types import AgentDefinition
from bootstrap import state

_GENERATION_PROMPT = """\
You are an elite AI agent architect. Your job is to translate a user's description into a precise, high-performance agent definition for Thrall — a stateful autonomous AI system.

When a user describes what they want an agent to do, you will:

1. **Extract Core Intent** — identify the fundamental purpose, key responsibilities, and success criteria.

2. **Design Expert Persona** — create a compelling expert identity with deep domain knowledge. The persona should guide the agent's decision-making.

3. **Write a Complete System Prompt** that:
   - Establishes clear behavioural boundaries and operating parameters
   - Provides specific methodologies and best practices
   - Anticipates edge cases
   - Defines output format expectations
   - Is written in second person ("You are...", "You will...")

4. **Select Tools** — from this list, pick only what the agent actually needs:
   filesystem.read, filesystem.write, filesystem.append, filesystem.edit,
   filesystem.glob, filesystem.grep, filesystem.ls, filesystem.tree,
   web.search, web.fetch, web.scrape,
   code.execute, memory.read, memory.write

5. **Create a Name** — a concise slug:
   - lowercase letters, numbers, hyphens only
   - 2-4 words joined by hyphens
   - clearly indicates primary function
   - no generic terms like "helper" or "assistant"
   - examples: code-reviewer, data-analyst, research-scout, log-monitor

6. **Write a Description** — one sentence starting with "Use this agent when..."

Return ONLY a valid JSON object, no other text:
{
  "name": "slug-name",
  "description": "Use this agent when...",
  "soul": "You are... [full system prompt]",
  "model": "meta-llama/llama-3.3-70b-instruct:free",
  "allowed_tools": ["tool1", "tool2"]
}
"""


async def generate(description: str, existing_names: list[str]) -> AgentDefinition:
    from services.llm import client as llm

    existing_note = ""
    if existing_names:
        existing_note = f"\n\nThese names are already taken — do not use them: {', '.join(existing_names)}"

    messages = [
        {"role": "system", "content": _GENERATION_PROMPT},
        {"role": "user", "content": f"Create an agent for: {description}{existing_note}\n\nReturn ONLY the JSON object."},
    ]

    cfg = state.get_config().get("llm", {})
    model = cfg.get("model", "meta-llama/llama-3.3-70b-instruct:free")

    raw = await llm.complete(messages, model=model)

    parsed = _parse_json(raw)

    return AgentDefinition(
        name=parsed["name"],
        description=parsed["description"],
        soul=parsed["soul"],
        model=parsed.get("model", model),
        allowed_tools=parsed.get("allowed_tools", []),
    )


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"No valid JSON found in LLM response: {text[:200]}")
