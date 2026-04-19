from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AgentDefinition:
    name: str                          # slug: lowercase, hyphens only
    description: str                   # when to use — one sentence
    soul: str                          # full system prompt
    model: str = "meta-llama/llama-3.3-70b-instruct:free"
    allowed_tools: list[str] = field(default_factory=lambda: [
        "filesystem.read", "filesystem.glob", "filesystem.grep",
        "filesystem.write", "filesystem.append",
        "web.fetch", "web.search", "web.scrape",
        "code.execute",
    ])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
