from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID
from schemas.message import Transport


@dataclass
class CommandContext:
    user_id: str
    session_id: UUID
    transport: Transport
    args: list[str]


class Command(ABC):
    @abstractmethod
    async def execute(self, ctx: CommandContext) -> str: ...

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def description(self) -> str: ...
