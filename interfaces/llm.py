from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncIterator
from schemas.llm import LLMResponse


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str: ...

    @abstractmethod
    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    def name(self) -> str: ...
