from __future__ import annotations
import asyncio
from typing import Callable, Awaitable
from uuid import UUID
from schemas.task import Task, TaskType, TaskStatus
from interfaces.task import BaseTask
from bootstrap import state

# Active task pool — single source of truth for all running workers.
# Tasks are asyncio.Task wrappers around BaseTask instances.

_pool: dict[UUID, tuple[BaseTask, asyncio.Task]] = {}
_completion_callbacks: list[Callable[[Task], Awaitable[None]]] = []


def register_completion_callback(fn: Callable[[Task], Awaitable[None]]) -> None:
    if fn not in _completion_callbacks:
        _completion_callbacks.append(fn)


async def submit(task: Task) -> BaseTask:
    worker = _build(task)
    loop_task = asyncio.create_task(_run(worker), name=f"task-{task.id}")
    _pool[task.id] = (worker, loop_task)
    state.increment_tasks()
    return worker


async def cancel(task_id: UUID) -> bool:
    if task_id not in _pool:
        return False
    worker, loop_task = _pool[task_id]
    await worker.cancel()
    loop_task.cancel()
    _pool.pop(task_id, None)
    return True


def get(task_id: UUID) -> BaseTask | None:
    entry = _pool.get(task_id)
    return entry[0] if entry else None


def list_active() -> list[Task]:
    return [entry[0].task for entry in _pool.values()]


def list_by_status(status: TaskStatus) -> list[Task]:
    return [t for t in list_active() if t.status == status]


def count() -> int:
    return len(_pool)


async def cancel_all() -> None:
    for task_id in list(_pool.keys()):
        await cancel(task_id)


async def _run(worker: BaseTask) -> None:
    try:
        await worker.run()
    finally:
        _pool.pop(worker.id, None)
        for cb in _completion_callbacks:
            try:
                await cb(worker.task)
            except Exception:
                pass


def _build(task: Task) -> BaseTask:
    if task.type == TaskType.LOCAL:
        from thrall.tasks.local_task import LocalTask
        return LocalTask(task)
    if task.type == TaskType.SHELL:
        from thrall.tasks.shell_task import ShellTask
        return ShellTask(task)
    if task.type == TaskType.REMOTE:
        from thrall.tasks.remote_task import RemoteTask
        return RemoteTask(task)
    raise ValueError(f"Unknown task type: {task.type}")
