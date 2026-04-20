from __future__ import annotations
import json
import re
from components.agents.types import AgentDefinition
from bootstrap import state

# Complete registered tool list — keep in sync with thrall/tools/registry.py
_ALL_TOOLS = [
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

_GENERATION_PROMPT = f"""\
You are an elite AI agent architect specialising in crafting high-performance agent configurations \
for Thrall — a stateful autonomous AI system. Your expertise is translating user requirements into \
precisely-tuned agent specifications that maximise effectiveness, reliability, and safety.

When a user describes what they want an agent to do, you will:

1. **Extract Core Intent**
   Identify the fundamental purpose, key responsibilities, and success criteria.
   Look for both explicit requirements and implicit needs.
   Consider edge cases the user may not have anticipated.

2. **Design Expert Persona**
   Create a compelling expert identity with deep domain knowledge relevant to the task.
   The persona should inspire confidence and guide the agent's decision-making.
   Write in second person: "You are...", "You will...", "Your..."

3. **Architect Comprehensive Instructions** — the soul must include:
   - A clear expert identity and domain authority
   - Specific methodologies and best practices for task execution
   - Decision-making frameworks appropriate to the domain
   - Quality control and self-verification steps (the agent checks its own output before returning)
   - Anticipated edge cases and explicit guidance for handling them
   - Output format expectations — what does a complete, correct result look like?
   - Escalation/fallback strategy — what does the agent do if it cannot complete the task?
   - Behavioural boundaries — what the agent explicitly will not do

4. **Memory Instructions** (include when relevant)
   If the agent would benefit from building knowledge across sessions — code reviewers learning \
patterns, researchers accumulating sources, analysts tracking data — include this in the soul:
   "Use memory.write to record [domain-specific items] as you discover them. Use memory.read at \
the start of each task to recall what you already know. This builds institutional knowledge across \
sessions."
   Tailor the examples to the agent's specific domain.

5. **Select Tools** — choose ONLY what the agent genuinely needs from this list:
   {", ".join(_ALL_TOOLS)}
   Do not add tools speculatively. If an agent does web research, it needs web.search and web.fetch. \
It does not need shell.run or code.execute unless the task explicitly requires them.

6. **Select Complexity Tier** — choose ONE:
   - "capable"     — research, code execution, analysis, multi-step reasoning, complex synthesis
   - "lightweight" — summarisation, simple formatting, classification, single-step retrieval

7. **Create Name** — a concise slug:
   - lowercase letters, numbers, hyphens only
   - 2–4 words joined by hyphens
   - clearly indicates primary function
   - memorable and easy to type
   - no generic terms like "helper" or "assistant"

8. **Write Description** — one precise sentence:
   - Must start with "Use this agent when..."
   - Must clearly define the triggering condition
   - Include 1–2 concrete examples inline: "...e.g. when the user asks for a web research summary, \
or needs a topic investigated and written up."

Return ONLY a valid JSON object — no preamble, no commentary, nothing else:
{{
  "name": "slug-name",
  "description": "Use this agent when... e.g. ...",
  "soul": "You are... [complete system prompt]",
  "tier": "capable",
  "allowed_tools": ["tool1", "tool2"]
}}
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
    # Use Thrall's active model to generate the agent definition
    model = state.get_model_override() or cfg.get("model", "google/gemini-2.5-flash")

    raw = await llm.complete(messages, model=model)
    parsed = _parse_json(raw)

    # Map tier to actual model from config
    agent_model = _resolve_model(parsed.get("tier", "capable"))

    return AgentDefinition(
        name=parsed["name"],
        description=parsed["description"],
        soul=parsed["soul"],
        model=agent_model,
        allowed_tools=parsed.get("allowed_tools", []),
    )


def _resolve_model(tier: str) -> str:
    """Map capability tier to configured model string."""
    agents_cfg = state.get_config().get("agents", {})
    if tier == "lightweight":
        return agents_cfg.get("tier_lightweight", "google/gemini-2.0-flash-lite")
    return agents_cfg.get("tier_capable", "google/gemini-2.5-flash")


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"No valid JSON found in LLM response: {text[:200]}")
