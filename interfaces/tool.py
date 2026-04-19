from __future__ import annotations
from abc import ABC, abstractmethod
from schemas.tool import ToolCall, ToolResult


class Tool(ABC):
    @abstractmethod
    async def execute(self, call: ToolCall) -> ToolResult: ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def parameters(self) -> dict: ...
