from __future__ import annotations
from datetime import datetime, timezone
from schemas.task import Task, TaskStatus
from interfaces.task import BaseTask
from bootstrap import state

# REMOTE TASK — placeholder
# Future: dispatch task to a remote agent endpoint (separate process, VM, or cloud worker).
# Remote tasks enable Thrall to offload long-running or resource-intensive work
# without blocking the main event loop.
#
# Implementation plan when ready:
# - POST brief + profile to remote agent URL
# - Poll or await webhook for result
# - Stream partial results back to pool
# - Handle reconnection and timeout


class RemoteTask(BaseTask):
    def __init__(self, task: Task) -> None:
        super().__init__(task)

    async def run(self) -> str:
        self.task.status = TaskStatus.FAILED
        self.task.error = "RemoteTask not yet implemented"
        self.task.completed_at = datetime.now(timezone.utc)
        state.decrement_tasks()
        return "error: RemoteTask not yet implemented"

    async def cancel(self) -> None:
        self.task.status = TaskStatus.CANCELLED
        self.task.completed_at = datetime.now(timezone.utc)
        state.decrement_tasks()
