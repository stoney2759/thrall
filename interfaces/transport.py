from __future__ import annotations
from abc import ABC, abstractmethod
from schemas.message import Message


class Transport(ABC):
    @abstractmethod
    async def send(self, user_id: str, content: str) -> None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def name(self) -> str: ...
