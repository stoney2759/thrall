from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from schemas.task import Task, TaskStatus
from interfaces.task import BaseTask
from bootstrap import state


class ShellTask(BaseTask):
    """Subprocess-based task for sandboxed code execution.
    Isolated from Thrall's process — can be killed cleanly."""

    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self._proc: asyncio.subprocess.Process | None = None

    async def run(self) -> str:
        self.task.status = TaskStatus.RUNNING
        self.task.started_at = datetime.now(timezone.utc)

        try:
            result = await self._execute()
            self.task.status = TaskStatus.DONE
            self.task.result = result
            self.task.completed_at = datetime.now(timezone.utc)
            return result
        except asyncio.CancelledError:
            await self._kill()
            self.task.status = TaskStatus.CANCELLED
            self.task.completed_at = datetime.now(timezone.utc)
            return "cancelled"
        except Exception as e:
            self.task.status = TaskStatus.FAILED
            self.task.error = str(e)
            self.task.completed_at = datetime.now(timezone.utc)
            state.log_error(f"ShellTask {self.task.id} failed: {e}")
            return f"error: {e}"
        finally:
            state.decrement_tasks()

    async def _execute(self) -> str:
        timeout = self.task.profile.max_duration_seconds

        self._proc = await asyncio.create_subprocess_shell(
            self.task.brief,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                self._proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await self._kill()
            return f"timed out after {timeout}s"

        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()

        if self._proc.returncode != 0:
            return f"exit {self._proc.returncode}\n{err or out}"

        return out or "(no output)"

    async def _kill(self) -> None:
        if self._proc:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass

    async def cancel(self) -> None:
        await self._kill()
        self.task.status = TaskStatus.CANCELLED
        self.task.completed_at = datetime.now(timezone.utc)
        state.decrement_tasks()
