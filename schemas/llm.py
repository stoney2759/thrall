from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ToolCallRequest:
    """A tool call requested by the LLM. Maps to Rust struct at port time."""
    id: str
    name: str
    args: dict


@dataclass
class LLMResponse:
    """Structured response from any LLM provider."""
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_final(self) -> bool:
        return not self.has_tool_calls
