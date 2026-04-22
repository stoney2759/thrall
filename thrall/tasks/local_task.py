from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from schemas.task import Task, TaskStatus
from schemas.tool import ToolCall
from interfaces.task import BaseTask
from services.llm import client as llm
from hooks import tool_gate
from bootstrap import state

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 8


class LocalTask(BaseTask):
    def __init__(self, task: Task) -> None:
        super().__init__(task)
        self._cancelled = False

    async def run(self) -> str:
        self.task = self.task.model_copy(update={
            "status": TaskStatus.RUNNING,
            "started_at": datetime.now(timezone.utc),
        })

        try:
            result = await self._reason()
            self.task = self.task.model_copy(update={
                "status": TaskStatus.DONE,
                "result": result,
                "completed_at": datetime.now(timezone.utc),
            })
            _store_result(self.task)
            return result
        except asyncio.CancelledError:
            self.task = self.task.model_copy(update={"status": TaskStatus.CANCELLED, "completed_at": datetime.now(timezone.utc)})
            _store_result(self.task)
            return "cancelled"
        except Exception as e:
            self.task = self.task.model_copy(update={"status": TaskStatus.FAILED, "error": str(e), "completed_at": datetime.now(timezone.utc)})
            _store_result(self.task)
            state.log_error(f"Agent {self.task.id} failed: {e}")
            return f"error: {e}"
        finally:
            state.decrement_tasks()

    async def _reason(self) -> str:
        from thrall.tools import registry as tools

        if self.task.soul_override:
            system = self.task.soul_override
        else:
            system = (
                f"You are a focused autonomous agent. "
                f"Profile: {self.task.profile.name}. "
                f"Allowed tools: {', '.join(self.task.profile.allowed_tools)}. "
                "Complete the task brief fully. Use your tools. Be concise in your final response."
            )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": self.task.brief},
        ]

        allowed = self.task.profile.allowed_tools
        tool_defs = tools.get_definitions(allowed=allowed)

        for _ in range(_MAX_ITERATIONS):
            if self._cancelled:
                return "cancelled"

            try:
                llm_response = await llm.complete_with_tools(messages, tool_defs)
            except Exception as e:
                logger.error(f"Agent {self.task.id} LLM call failed at iteration {_}: {e}", exc_info=True)
                raise

            if llm_response.is_final:
                return llm_response.content or ""

            # Add assistant turn
            messages.append({
                "role": "assistant",
                "content": llm_response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                    }
                    for tc in llm_response.tool_calls
                ],
            })

            # Execute each tool call
            for tc in llm_response.tool_calls:
                tool_call = ToolCall(
                    session_id=self.task.id,
                    name=tc.name,
                    args=tc.args,
                    caller=f"agent:{self.task.id}",
                )
                if not tool_gate.is_allowed(tool_call, self.task.profile):
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": "denied: not in capability profile"})
                    continue

                result = await tools.execute(tc.name, tc.args, self.task.id, f"agent:{self.task.id}")
                output = result.output or result.error or "(no output)"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

        # Max iterations — get final answer
        messages.append({"role": "user", "content": "Provide your final answer based on what you have gathered."})
        return await llm.complete(messages)

    async def cancel(self) -> None:
        self._cancelled = True
        self.task = self.task.model_copy(update={"status": TaskStatus.CANCELLED, "completed_at": datetime.now(timezone.utc)})
        _store_result(self.task)
        state.decrement_tasks()


def _store_result(task: Task) -> None:
    from thrall.tasks.result_store import set_result
    set_result(task.id, task.status, task.result, task.error)
