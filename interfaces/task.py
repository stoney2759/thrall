from __future__ import annotations
from abc import ABC, abstractmethod
from schemas.task import Task, TaskStatus


class BaseTask(ABC):
    def __init__(self, task: Task) -> None:
        self.task = task

    @abstractmethod
    async def run(self) -> str: ...

    @abstractmethod
    async def cancel(self) -> None: ...

    @property
    def id(self):
        return self.task.id

    @property
    def status(self) -> TaskStatus:
        return self.task.status
