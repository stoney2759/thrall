from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ToolCallRequest:
    """A tool call requested by the LLM. Maps to Rust struct at port time."""
    id: str
    name: str
    args: dict


@dataclass
class LLMUsage:
    """Token usage from an LLM response."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class LLMResponse:
    """Structured response from any LLM provider."""
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    reasoning: str | None = None
    reasoning_details: list[dict] = field(default_factory=list)
    usage: LLMUsage = field(default_factory=LLMUsage)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_final(self) -> bool:
        return not self.has_tool_calls

    @property
    def was_truncated(self) -> bool:
        return self.finish_reason == "length"
