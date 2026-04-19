from __future__ import annotations
from abc import ABC, abstractmethod


class BaseTransport(ABC):
    """Base class for all transports. Becomes a Rust trait at port time.
    Each transport is a dumb pipe — it converts its native message format
    into a Message schema and hands it to coordinator.receive()."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def name(self) -> str: ...
